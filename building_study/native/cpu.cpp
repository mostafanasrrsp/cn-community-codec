// One CPU thread, decoded shape records, and prepared source frames. Both arms
// of a pair integrate exactly the same rays in the same order.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <vector>

using Vec = std::array<double,3>;
using Face = std::array<double,4>;
using Faces = std::array<Face,4>;
struct Shape { std::array<double,6> w; Faces exact, decoded; };
struct Query {
    int shape, expected;
    Vec axis;
    double half, tau, c, denom;
    std::vector<Vec> transverse;
};
constexpr double guard = 0x1p-44;
constexpr double pi = 3.14159265358979323846;

bool excludes(const Faces& faces, const Query& q) {
    for (const auto& f : faces) {
        double dot = (f[0]*q.axis[0] + f[1]*q.axis[1]) + f[2]*q.axis[2];
        if (dot > f[3]*q.tau + guard) return true;
    }
    return false;
}
bool skip(const Shape& s, const Query& q) {
    return q.axis[2] > q.tau + guard && excludes(s.exact,q) && excludes(s.decoded,q);
}

Vec cross(Vec a, Vec b) {
    return {a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]};
}
struct Node { double x, weight; };
std::vector<Node> gauss(int n) {
    std::vector<Node> rule(n);
    for (int i=0; i<(n+1)/2; ++i) {
        double x=std::cos(pi*(i+0.75)/(n+0.5)), derivative=0;
        for (int iter=0; iter<30; ++iter) {
            double p=1, prev=0;
            for (int j=1; j<=n; ++j) {
                double next=((2*j-1)*x*p-(j-1)*prev)/j;
                prev=p; p=next;
            }
            derivative=n*(x*p-prev)/(x*x-1);
            double next=x-p/derivative;
            if (std::abs(next-x)<1e-16) break;
            x=next;
        }
        double weight=1/((1-x*x)*derivative*derivative);
        rule[i]={(1-x)/2,weight}; rule[n-1-i]={(1+x)/2,weight};
    }
    return rule;
}
void prepare(Query& q, int m) {
    Vec e=cross(std::abs(q.axis[2])>.8 ? Vec{1,0,0} : Vec{0,0,1},q.axis);
    double norm=std::sqrt(e[0]*e[0]+e[1]*e[1]+e[2]*e[2]);
    for (auto& x:e) x/=norm;
    Vec f=cross(q.axis,e);
    q.c=std::cos(pi*q.half/180);
    q.denom=q.axis[2]*(1+q.c)/2;
    for (int j=0;j<m;++j) {
        double p=2*pi*j/m;
        Vec dir{};
        for (int k=0;k<3;++k) dir[k]=std::cos(p)*e[k]+std::sin(p)*f[k];
        q.transverse.push_back(dir);
    }
}
double integrate(const Shape& shape, const Query& q, const std::vector<Node>& nodes) {
    double total=0;
    const auto& w=shape.w;
    for (const auto& node : nodes) {
        double u=q.c+(1-q.c)*node.x;
        double r=std::sqrt((1-u)*(1+u));
        double weight=node.weight/q.transverse.size()/q.denom;
        Vec center{u*q.axis[0],u*q.axis[1],u*q.axis[2]};
        for (const auto& dir : q.transverse) {
            double z=center[2]+r*dir[2];
            double x=(center[0]+r*dir[0])/z, y=(center[1]+r*dir[1])/z;
            double q0=w[0]*x+w[1]*y+w[4], q1=w[2]*x+w[3]*y+w[5];
            total+=weight*z*std::max(0.,1-std::abs(q0))*std::max(0.,1-std::abs(q1));
        }
    }
    return total;
}
template<bool gated>
__attribute__((noinline)) double pass(const std::vector<Shape>& shapes, const std::vector<Query>& queries,
        const std::vector<int>& order, const std::vector<Node>& nodes) {
    double total=0;
    for (auto i : order) {
        const auto& q=queries[i];
        const auto& s=shapes[q.shape];
        total+=gated && skip(s,q) ? 0 : integrate(s,q,nodes);
    }
    return total;
}
volatile double consume=0;
void array(const std::vector<double>& values) {
    std::cout<<"[";
    for (size_t i=0;i<values.size();++i) std::cout<<(i?",":"")<<values[i];
    std::cout<<"]";
}
int main(int argc, char** argv) {
    if (argc!=4) return 2;
    std::ifstream f(argv[1]);
    int radial=std::stoi(argv[2]), repeats=std::stoi(argv[3]);
    size_t n=0,m=0;
    if (!(f>>n>>m) || n==0 || m==0) return 2;
    std::vector<Shape> shapes(n);
    for (auto& shape:shapes) {
        for (auto& v:shape.w) f>>v;
        for (auto* faces:{&shape.exact,&shape.decoded})
            for (auto& face:*faces) for(auto& v:face) f>>v;
    }
    auto rule=gauss(radial);
    std::vector<Query> queries(m);
    std::vector<double> outputs;
    for (auto& q:queries) {
        f>>q.shape>>q.axis[0]>>q.axis[1]>>q.axis[2]>>q.half>>q.tau>>q.expected;
        if (!f || q.shape<0 || q.shape>=int(n)) throw std::runtime_error("malformed input");
        prepare(q,4*radial);
        const auto& s=shapes[q.shape];
        bool proof=skip(s,q);
        if (proof!=bool(q.expected)) throw std::runtime_error("native vs rational skip mismatch");
        double v=integrate(s,q,rule);
        if (!std::isfinite(v) || (proof && v!=0)) throw std::runtime_error("changed query");
        outputs.push_back(v);
    }
    std::vector<int> order(m); std::iota(order.begin(),order.end(),0);
    std::mt19937 rng(20261106);
    std::shuffle(order.begin(),order.end(),rng);
    consume=pass<false>(shapes,queries,order,rule);
    consume=pass<true>(shapes,queries,order,rule);
    std::vector<double> baseline(repeats), gated(repeats);
    const int inner = 3;
    // Each sample is a whole panel. Re-shuffle between pairs to reduce
    // sensitivity to query order; cached source coordinates serve both arms.
    for (int trial=0;trial<repeats;++trial) {
        std::shuffle(order.begin(),order.end(),rng);
        for (int arm=0;arm<2;++arm) {
            bool gate=(arm+trial)%2;
            auto start=std::chrono::steady_clock::now();
            for (int loop=0;loop<inner;++loop) {
                // Prevent hoisting an entire repeated traversal out of the timer.
                asm volatile("" ::: "memory");
                consume=gate ? pass<true>(shapes,queries,order,rule) : pass<false>(shapes,queries,order,rule);
            }
            auto end=std::chrono::steady_clock::now();
            (gate?gated:baseline)[trial]=std::chrono::duration<double,std::milli>(end-start).count()/inner;
        }
    }
    std::cout<<std::setprecision(17)<<"{\"panels_per_sample\":"<<inner<<",\"baseline_ms\":"; array(baseline);
    std::cout<<",\"gated_ms\":"; array(gated);
    std::cout<<",\"outputs\":"; array(outputs); std::cout<<"}\n";
}
