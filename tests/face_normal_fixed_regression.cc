// Compile with SCALAR_TYPE_FIXED. Checks coordinates after 16.16 quantization.
#include <gfx/face.hp>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <random>

static Vector3 v(int32_t x,int32_t y,int32_t z) {
    return Vector3(Scalar::FromFixed32(x),Scalar::FromFixed32(y),Scalar::FromFixed32(z));
}
int main() {
    Vector3 n=CalculateNormal(v(0,0,0),v(66,0,0),v(0,66,0));
    assert(std::fabs(n.Z().AsFloat()-1)<0.0001);
    n=CalculateNormal(v(0,0,0),v(0,66,0),v(66,0,0));
    assert(std::fabs(n.Z().AsFloat()+1)<0.0001);
    n=CalculateNormal(v(0,0,0),v(0,0,0),v(0,66,0));
    assert(n.X().AsLong()==0 && n.Y().AsLong()==0 && n.Z().AsLong()==0);
    // Exercise 33-bit coordinate differences and near-parallel cancellation.
    assert(FaceCrossComponent(4294967295LL,4294967295LL,4294967294LL,4294967296LL)==1.0);
    std::mt19937_64 gen(7);
    for (int i=0;i<100000;++i) {
        int64_t a=int64_t(uint32_t(gen()))-int64_t(uint32_t(gen()));
        int64_t b=int64_t(uint32_t(gen()))-int64_t(uint32_t(gen()));
        int64_t c=int64_t(uint32_t(gen()))-int64_t(uint32_t(gen()));
        int64_t d=int64_t(uint32_t(gen()))-int64_t(uint32_t(gen()));
        __int128 exact=__int128(a)*b-__int128(c)*d;
        double expected=double(exact), actual=FaceCrossComponent(a,b,c,d);
        assert(std::fabs(actual-expected)<=std::fabs(expected)*5e-16);
    }
}
