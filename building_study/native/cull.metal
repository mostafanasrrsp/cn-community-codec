#include <metal_stdlib>
using namespace metal;

constant bool useCull [[function_constant(0)]];
struct Result { float value; uint skipped; };
struct Shape { float4 w, bias; float4 faces[12]; };
struct Query { float4 axisTau, eCos, fDenom; uint shape; uint reserved[3]; };

// The input generator normalizes each face to a maximum absolute component of one.
// The margin covers fp32 conversion and arithmetic on the bounded normalized vectors.
bool misses(device const float4* faces, float4 axisTau) {
    constexpr float guard = 0x1p-15f;
    for (uint j = 0; j < 4; ++j) {
        float4 face = faces[j];
        if (dot(face.xyz,axisTau.xyz) > face.w * axisTau.w + guard) return true;
    }
    return false;
}

kernel void solve(device const Shape* shapes [[buffer(0)]],
                  device const Query* queries [[buffer(1)]],
                  device const float2* radial [[buffer(2)]],
                  device const float2* azimuth [[buffer(3)]],
                  device const uint* order [[buffer(4)]],
                  device Result* out [[buffer(5)]],
                  constant uint& n [[buffer(6)]],
                  uint lane [[thread_index_in_simdgroup]],
                  uint3 group [[threadgroup_position_in_grid]]) {
    uint index = order[group.x];
    Query q = queries[index];
    device const Shape &s = shapes[q.shape];
    bool empty = false;
    if (useCull) {
        if (lane == 0 && q.axisTau.z > q.axisTau.w + 0x1p-15f) {
            empty = misses(s.faces, q.axisTau) && misses(s.faces + 4, q.axisTau)
                && misses(s.faces + 8, q.axisTau);
        }
        empty = simd_broadcast_first(uint(empty)) != 0;
    }
    if (empty) {
        if (!lane) out[index] = {0.0f,1};
        return;
    }
    const uint angles = 4*n;
    float total = 0;
    // Each SIMD group owns one cone. Lanes stride over azimuth angles.
    for (uint j = lane; j < angles; j += 32) {
        float2 a = azimuth[j];
        float3 transverse = a.x*q.eCos.xyz + a.y*q.fDenom.xyz;
        for (uint i = 0; i < n; ++i) {
            float2 r = radial[i];
            float u = q.eCos.w + (1.0f - q.eCos.w)*r.x;
            float3 ray = u*q.axisTau.xyz + sqrt((1.0f-u)*(1.0f+u))*transverse;
            float2 p = ray.xy/ray.z;
            float x = dot(s.w.xy,p) + s.bias.x;
            float y = dot(s.w.zw,p) + s.bias.y;
            total += r.y * ray.z * max(0.0f,1.0f-abs(x)) * max(0.0f,1.0f-abs(y));
        }
    }
    float value = simd_sum(total)/(float(angles)*q.fDenom.w);
    if (!lane) out[index] = {value,0};
}
