#include <gfx/face.hp>
#include <cstdio>
#include <vector>
#include <chrono>
#include <cstdint>
struct Tri { Vector3 a,b,c; };
unsigned long
Sqrt64(long __a1,long __a0)
{
	unsigned long __t1;
	unsigned long __t2;
	register unsigned long __Estimate;
	register unsigned long __EstimateX2;
	unsigned long __Error;
	int __i;

	//  result = sqrt(a1:a0)

	__Estimate = __EstimateX2 = __Error = 0;
	__t1 = __a0;
	__t2 = __a1;

	for(__i=0; __i<16; ++__i) 			// 16 bit pairs from high dword
	{
		ShiftLeft64(__Error,__t2,2); // 2 bits into error

		__Estimate <<= 1;		// estimate *= 2
		__EstimateX2 <<= 1;

		if (__EstimateX2 < __Error) 		// if estimate*2 < error
		{

			__Error -= __EstimateX2 + 1;	// update error
			++__Estimate;					// set low bit of estimate
			__EstimateX2 += 2;				// set bit 1 of estimate*2
		}
	}

	for(__i=0; __i<16; ++__i) 				// 16 bit pairs from low dword
	{

		ShiftLeft64(__Error,__t1,2); 		// 2 bits into error

		__Estimate <<= 1;					// estimate *=2
		__EstimateX2 <<= 1;

		if(__EstimateX2 < __Error) 			// if estimate*2 < error
		{
			__Error -= __EstimateX2 + 1;	// update error
			++__Estimate;					// set low bit of estimate
			__EstimateX2 += 2;				// set low bit of estimate*2
		}
	}
	return(__Estimate);
}

Vector3
Vector3::CrossProduct(const Vector3& other) const
{
	Vector3 result;

	result.SetX((Y()*other.Z())-(Z()*other.Y()));
	result.SetY((Z()*other.X())-(X()*other.Z()));
	result.SetZ((X()*other.Y())-(Y()*other.X()));
	return(result);
}

//-----------------------------------------------------------------------------

Scalar
Vector3::Length() const
{
#if defined(SCALAR_TYPE_FIXED)
	int32 a = X().AsLong();
	int32 b = Y().AsLong();
	int32 c = Z().AsLong();
    register unsigned long out0;
	register long out1;
	register unsigned long out2;
	register long out3;

	// result = sqrt(a*a + b*b + c*c)
	MultiplyAndNop64(a,a,out1,out0);

	Multiply64(b,b,out3,out2);

	AddCarry64(out1,out0,out3,out2);

	Multiply64(c,c,out3,out2);

	AddCarry64(out1,out0,out3,out2);

	Scalar result(static_cast<long>(Sqrt64(out1,out0)));
//	cscreen << "len: " << *this << endl;
//	cscreen << "out1:" << out1 << ",out2:" << out2 << endl;
//	cscreen << "result: " << result << endl;
	return result;
#elif defined(SCALAR_TYPE_FLOAT) || defined(SCALAR_TYPE_DOUBLE)
   return ((X()*X()) + (Y()*Y()) + (Z()*Z())).Abs().Sqrt();
#else
#error SCALAR TYPE not defined
#endif
}


int main(int argc,char**argv){if(argc!=2)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 3;std::vector<Tri> t;int32_t x[9];while(fread(x,4,9,f)==9){Vector3 a(Scalar::FromDouble(x[0]/65536.0),Scalar::FromDouble(x[1]/65536.0),Scalar::FromDouble(x[2]/65536.0));Vector3 b(Scalar::FromDouble(x[3]/65536.0),Scalar::FromDouble(x[4]/65536.0),Scalar::FromDouble(x[5]/65536.0));Vector3 c(Scalar::FromDouble(x[6]/65536.0),Scalar::FromDouble(x[7]/65536.0),Scalar::FromDouble(x[8]/65536.0));t.push_back({a,b,c});}fclose(f);volatile long long sum=0;auto a=std::chrono::steady_clock::now();for(int j=0;j<25;++j)for(auto const&x:t){Vector3 n=CalculateNormal(x.a,x.b,x.c);sum+=n.X().AsLong()+n.Y().AsLong()+n.Z().AsLong();}auto b=std::chrono::steady_clock::now();printf("faces=%zu nanos=%lld checksum=%lld\n",t.size(),(long long)std::chrono::duration_cast<std::chrono::nanoseconds>(b-a).count(),sum);}
