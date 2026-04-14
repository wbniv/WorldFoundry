//==============================================================================
// pixelmap.cc: rectangle of pixels, either in main memory or video memory
// Copyright ( c ) 1997,1998,1999,2000,2001,2002 World Foundry Group.  
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// Version 2 as published by the Free Software Foundation
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
// or see www.fsf.org

//==============================================================================
// Original Author: Kevin T. Seghetti
//==============================================================================

#include <pigsys/pigsys.hp>
#include <gfx/pixelmap.hp>
#include <gfx/renderer.hp>


#pragma pack( 1 )
struct RGB_pixel
{
	unsigned char r, g, b;
};
#pragma pack( 4 )

//==============================================================================

PixelMap::PixelMap(int flags, int xSize, int ySize)
{
	assert(flags == MEMORY_VIDEO);

	//assert(xSize == Display::VRAMWidth);
	//assert(ySize == Display::VRAMHeight);

	_flags = flags;
	_xPos = 0;
	_yPos = 0;
	_xSize = xSize;
	_ySize = ySize;

    _parent = NULL;
#if SIXTEEN_BIT_VRAM
     _pixelBuffer = new uint16[xSize*ySize];
#else
    _pixelBuffer = new GLubyte[xSize*ySize*4];
#endif		                            // sixteen_bit
    ValidatePtr(_pixelBuffer);

   AssertGLOK();
    glGenTextures(1,&_glTextureName);
    assert(_glTextureName);
   AssertGLOK();



	Validate();
    //std::cout << "PixelMap::PixelMap: this = " << *this << std::endl;
}

//=============================================================================

PixelMap::PixelMap(PixelMap& parent,int xPos, int yPos, int xSize, int ySize)
{
	parent.Validate();

	_flags = parent._flags;

	assert(xPos >= 0);
	assert(yPos >= 0);
	assert(xPos <= parent._xSize);
	assert(yPos <= parent._ySize);
	assert(xSize <= parent._xSize);
	assert(ySize <= parent._ySize);
	assert(xPos + xSize <= parent._xSize);
	assert(yPos + ySize <= parent._ySize);

	_xPos = parent._xPos + xPos;
	_yPos = parent._yPos + yPos;

	_xSize = xSize;
	_ySize = ySize;
    _parent = &parent;
    _pixelBuffer = NULL;
	Validate();
    std::cout << "PixelMap::PixelMap: subpixelmap = " << this << std::endl;
}

//==============================================================================

PixelMap::~PixelMap()
{
    Validate();
    if(_pixelBuffer)
        delete [] _pixelBuffer;
    glDeleteTextures(1,(GLuint*)&_glTextureName);
}

//==============================================================================

void
PixelMap::Load(const void* memory, int xSize, int ySize) 
{
    Load(memory, 0, 0, xSize, ySize);
}

//==============================================================================

void
PixelMap::Load(const void* memory, int xOffset, int yOffset, int xSize, int ySize) 
{
    std::cout << "PixelMap::Load: this = " << (void*)this << std::endl;
//    std::cout << "PixelMap::load: " << xOffset << "," << yOffset << "," << xSize << "," << ySize << std::endl;
//    std::cout << "PixelMap::Load: xSize = " << xSize << ", ySize = " << ySize << std::endl;
//	std::cout << *this << std::endl;
	Validate();
	assert(memory);
    RangeCheck(0,xOffset,_xSize);
    RangeCheck(0,yOffset,_ySize);
	AssertMsg(xOffset+xSize <= _xSize,"xOffset = " << xOffset << ", xSize = " << xSize << ", xOffset+xSize = " << xOffset+xSize << ", _xSize = " << _xSize << "PixelMap:" << *this);
	AssertMsg(yOffset+ySize <= _ySize,"yOffset+ySize = " << yOffset+ySize << ", _ySize = " << _ySize);


     if(_parent)
     {
         //std::cout << "PM::L:calling parent with " << xOffset << "," << _xPos << "," << yOffset << "," << _yPos << "," << xSize << "," << ySize << std::endl;
         _parent->Load(memory,xOffset+_xPos,yOffset+_yPos,xSize,ySize);
         return;             // kts ugly
     }



    psxRECT rect;
    rect.x = _xPos+xOffset;
    rect.y = _yPos+yOffset;
    rect.w = xSize;
    rect.h = ySize;

    long unsigned int * _p = (long unsigned int *)memory;
    ValidatePtr(_pixelBuffer);
    GLubyte* pPB = _pixelBuffer;

//	std::cout << "loading image into vram:" << rect.x << "," << rect.y << ";" << rect.w << "," << rect.h << std::endl;
	assert(ValidPtr(_p));

	uint16* pixels = (uint16*)_p;

	int x2 = rect.x + rect.w;
	int y2 = rect.y + rect.h;

	assert(rect.x >= 0);
	assert(x2 <= GetXSize());
	assert(rect.y >= 0);
	assert(y2 <= GetYSize());

	for ( int y=rect.y; y<y2; ++y )
	{
		for ( int x=rect.x; x<x2; ++x )
		{
            assert(pPB);
            GLubyte* destPixel = pPB + ((y*_xSize) + x)*4;            // 4 bytes per pixel: R, G, B, A
#if SIXTEEN_BIT_VRAM
			*destPixel = *pixels;
#else
            assert(destPixel);
			destPixel[0] = ((*pixels >> 10) & 0x1f) << 3;
			destPixel[1] = ((*pixels >> 5) & 0x1f) << 3;
			destPixel[2] = (*pixels & 0x1f) << 3;
			if(*pixels == 0x8000)
				destPixel[3] = 255;	// be black
			else if(*pixels == 0)
				destPixel[3] = 0;  	// be transparent
			else if(*pixels & 0x8000)
				destPixel[3] = 128;  	// be semi-transparent
			else
				destPixel[3] = 255;	// be solid
#endif // SIXTEEN_BIT_VRAM
			pixels++;
		}
	}

    if(_flags == MEMORY_VIDEO)
    {
        AssertGLOK();

        assert(_glTextureName);
        glBindTexture(GL_TEXTURE_2D,_glTextureName);

#if SIXTEEN_BIT_VRAM
#define TEXTURE_INTERNAL_FORMAT GL_RGB5
#define TEXTURE_FORMAT GL_RGB
#else
#define TEXTURE_INTERNAL_FORMAT GL_RGBA
#define TEXTURE_FORMAT GL_RGBA
#endif


        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
        AssertGLOK();
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT);
        AssertGLOK();
#if defined ( GFX_ZBUFFER )
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        AssertGLOK();
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        AssertGLOK();
        glEnable(GL_DEPTH_TEST);
        AssertGLOK();
        glEnable(GL_BLEND);
        AssertGLOK();
#else /* GFX_ZBUFFER */
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        AssertGLOK();
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        AssertGLOK();
#endif /* GFX_ZBUFFER */

          glTexImage2D(GL_TEXTURE_2D, 0, TEXTURE_INTERNAL_FORMAT, _xSize, _ySize,
                  0, TEXTURE_FORMAT, GL_UNSIGNED_BYTE, pPB);
        AssertGLOK();
//        // kts temp code
//          char* foo = new char[_xSize*_ySize*4];
//          assert(foo);
//          for(int index = 0; index < (_xSize*_ySize*4);index++)
//              foo[index] = 0x0;

//             glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, _xSize, _ySize,
//                     0, GL_RGBA, GL_UNSIGNED_BYTE, foo);
//   AssertGLOK();

//             delete [] foo;


        AssertGLOK();
    }

}

//==============================================================================

#if DO_IOSTREAMS

std::ostream&
operator << ( std::ostream& s, const PixelMap& p )
{
	s << "PixelMap: " << std::endl;
	s << "  xPos : " << p._xPos << std::endl;
	s << "  yPos : " << p._yPos << std::endl;
	s << "  xSize: " << p._xSize << std::endl;
	s << "  ySize: " << p._ySize << std::endl;
	s << "  flags: " << p._flags;
	return s;
}

#endif // DO_IOSTREAMS

//==============================================================================
