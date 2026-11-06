// Calls the actual inline function used by RenderObject3D's FACE loader.
#include <gfx/face.hp>
#include <cstdio>
#include <cstdlib>
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const float edge=std::strtof(argv[1], nullptr);
    const Vector3 a(Scalar::FromFloat(0),Scalar::FromFloat(0),Scalar::FromFloat(0));
    const Vector3 b(Scalar::FromFloat(edge),Scalar::FromFloat(0),Scalar::FromFloat(0));
    const Vector3 c(Scalar::FromFloat(0),Scalar::FromFloat(edge),Scalar::FromFloat(0));
    const Vector3 n=CalculateNormal(a,b,c);
    std::printf("edge=%.9g normal=(%.9g,%.9g,%.9g)\n",edge,n.X().AsFloat(),n.Y().AsFloat(),n.Z().AsFloat());
}
