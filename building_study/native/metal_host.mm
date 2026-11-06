// Each command buffer visits the front-facing window queries for one weather year.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <vector>

using Clock=std::chrono::steady_clock;
struct Pair { float x,y; };
struct Result { float value; uint32_t skipped; };
struct Timing { double gpuMS,wallMS,readUS; };

std::vector<Pair> gauss(int n) {
    std::vector<Pair> result(n);
    for(int i=0;i<(n+1)/2;i++) {
        double x=std::cos(M_PI*(i+.75)/(n+.5)), dp=0;
        for(int iter=0;iter<30;++iter) {
            double p=1, prev=0;
            for(int j=1;j<=n;++j) {
                double next=((2*j-1)*x*p-(j-1)*prev)/j;
                prev=p; p=next;
            }
            dp=n*(x*p-prev)/(x*x-1);
            double next=x-p/dp;
            if(std::abs(next-x)<1e-16) break;
            x=next;
        }
        float w=1/((1-x*x)*dp*dp);
        result[i]={float((1-x)/2),w}; result[n-1-i]={float((1+x)/2),w};
    }
    return result;
}
template<class T> void read(std::ifstream& f,T* v,size_t n) {
    if (!f.read(reinterpret_cast<char*>(v),sizeof(T)*n)) throw std::runtime_error("short input");
}
int main(int argc,char** argv) {
    if(argc!=4) return 2;
    @autoreleasepool {
        uint32_t n=std::stoi(argv[3]);
        std::ifstream f(argv[2],std::ios::binary);
        uint32_t counts[2]; read(f,counts,2);
        // Small local research files only. Validate the declared length before allocating.
        if (counts[0]==0 || counts[0]>4096 || counts[1]==0 || counts[1]>100000 || n!=8) return 2;
        f.seekg(0, std::ios::end);
        if (f.tellg()!=std::streamoff(8+uint64_t(counts[0])*224+uint64_t(counts[1])*64)) return 2;
        f.seekg(8);
        std::vector<float> shapes(counts[0]*56);
        std::vector<char> queries(counts[1]*64);
        read(f,shapes.data(),shapes.size()); read(f,queries.data(),queries.size());
        if(f.peek()!=EOF) return 2;
        auto device=MTLCreateSystemDefaultDevice();
        auto queue=[device newCommandQueue];
        NSError *err=nil;
        auto lib=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&err];
        if(!lib || !queue) { NSLog(@"Metal unavailable: %@",err); return 1; }
        id<MTLComputePipelineState> pipelines[2];
        for(int arm=0;arm<2;arm++){
            bool gate=bool(arm);
            auto spec=[MTLFunctionConstantValues new];
            [spec setConstantValue:&gate type:MTLDataTypeBool atIndex:0];
            auto fn=[lib newFunctionWithName:@"solve" constantValues:spec error:&err];
            pipelines[arm]=fn ? [device newComputePipelineStateWithFunction:fn error:&err] : nil;
            if(!pipelines[arm] || pipelines[arm].threadExecutionWidth!=32) {
                NSLog(@"Single 32-wide SIMD group required: %@",err); return 1;
            }
        }
        auto buffer=[&](const void* bytes,size_t len) {
            return [device newBufferWithBytes:bytes length:len options:MTLResourceStorageModeShared];
        };
        auto radial=gauss(n);
        std::vector<Pair> az(4*n);
        for(size_t j=0;j<az.size();j++){
            double angle=2*M_PI*j/az.size();
            az[j]={float(std::cos(angle)),float(std::sin(angle))};
        }
        std::vector<uint32_t> order(counts[1]); std::iota(order.begin(),order.end(),0);
        std::mt19937 rng(20261106);
        id<MTLBuffer> shared[6] = {
            buffer(shapes.data(),sizeof(float)*shapes.size()),
            buffer(queries.data(),queries.size()),
            buffer(radial.data(),sizeof(Pair)*radial.size()),
            buffer(az.data(),sizeof(Pair)*az.size()),buffer(order.data(),sizeof(uint32_t)*order.size()),
            [device newBufferWithLength:sizeof(Result)*order.size() options:MTLResourceStorageModeShared]
        };
        std::vector<Result> copied[2]={std::vector<Result>(order.size()),std::vector<Result>(order.size())};
        auto launch=[&](int arm) -> Timing {
            @autoreleasepool {
                const auto start=Clock::now();
                auto cmd=[queue commandBuffer];
                auto enc=[cmd computeCommandEncoder];
                [enc setComputePipelineState:pipelines[arm]];
                for(NSUInteger i=0;i<6;i++) [enc setBuffer:shared[i] offset:0 atIndex:i];
                [enc setBytes:&n length:sizeof(n) atIndex:6];
                [enc dispatchThreadgroups:MTLSizeMake(order.size(),1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
                [enc endEncoding]; [cmd commit]; [cmd waitUntilCompleted];
                const auto completed=Clock::now();
                if(cmd.status!=MTLCommandBufferStatusCompleted) {
                    NSLog(@"Command failed: %@",cmd.error); std::abort();
                }
                const auto readStart=Clock::now();
                std::memcpy(copied[arm].data(),shared[5].contents,sizeof(Result)*order.size());
                const auto readDone=Clock::now();
                return {(cmd.GPUEndTime-cmd.GPUStartTime)*1000,
                    std::chrono::duration<double,std::milli>(completed-start).count(),
                    std::chrono::duration<double,std::micro>(readDone-readStart).count()};
            }
        };
        NSMutableDictionary *result=[@{@"device":device.name,@"simd_width":@32,@"paired_trials":@21} mutableCopy];
        for(NSString* prefix in @[@"base_",@"cull_"])
            for(NSString* suffix in @[@"gpu_ms",@"wall_ms",@"read_us"])
                result[[prefix stringByAppendingString:suffix]]=[NSMutableArray array];
        for(int trial=-4;trial<21;trial++){
            std::shuffle(order.begin(),order.end(),rng);
            std::memcpy(shared[4].contents,order.data(),order.size()*sizeof(uint32_t));
            for(int j=0;j<2;j++){
                int arm=(j+trial+4)%2; Timing t=launch(arm);
                if(trial<0) continue;
                auto k=arm?@"cull_":@"base_";
                [result[[k stringByAppendingString:@"gpu_ms"]] addObject:@(t.gpuMS)];
                [result[[k stringByAppendingString:@"wall_ms"]] addObject:@(t.wallMS)];
                [result[[k stringByAppendingString:@"read_us"]] addObject:@(t.readUS)];
            }
            for(size_t j=0;j<order.size();j++)
                if(copied[0][j].skipped!=0 ||
                   std::memcmp(&copied[0][j].value,&copied[1][j].value,sizeof(float))!=0) {
                    fprintf(stderr,"result mismatch %zu (%g vs %g)\n",j,copied[0][j].value,copied[1][j].value); return 3;
                }
        }
        NSMutableArray *values=[NSMutableArray array], *flags=[NSMutableArray array];
        for(auto r:copied[1]) { [values addObject:@(r.value)]; [flags addObject:@(r.skipped)]; }
        result[@"values"]=values; result[@"skipped"]=flags;
        NSData *json=[NSJSONSerialization dataWithJSONObject:result options:0 error:&err];
        if(!json){NSLog(@"serialization error %@",err); return 3;}
        fwrite(json.bytes,1,json.length,stdout); putchar('\n');
    }
}
