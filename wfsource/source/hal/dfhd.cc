//=============================================================================
// DiskFileHD.cc:
// Copyright ( c ) 1996,97,99,2026 World Foundry Group
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

// ===========================================================================
// Description: DiskFileHD — reads bundled game assets (cd.iff) through the
// platform-agnostic AssetAccessor interface. POSIX fd / AAssetManager /
// future backends all look the same from here.
// Original Author: Kevin T. Seghetti
//============================================================================

#include <pigsys/pigsys.hp>
#include <hal/diskfile.hp>
#include <hal/asset_accessor.hp>

extern void InitSimpleDisplay();
extern void UpdateSimpleDisplay();

//=============================================================================

#define DO_HDUMP 0

//=============================================================================

void
HalInitFileSubsystem()
{
}

//=============================================================================

void
DiskFileHD::Validate() const
{
	_DiskFile::Validate();
	assert(_fileHandle);
}

//=============================================================================


DiskFileHD::DiskFileHD( const char* fileName ) : _DiskFile( fileName )
{
	_currentFilePosition = 0;
	_hasSeeked = false;

	AssetAccessor& fs = HALGetAssetAccessor();
	_fileHandle = fs.OpenForRead(fileName);
	AssertMsg( _fileHandle, "filename = " << fileName );
	if ( _fileHandle )
	{
#if DO_ASSERTIONS
		_fileSize = static_cast<int32>(fs.Size(_fileHandle));
#endif
		int64_t seekok = fs.SeekAbsolute(_fileHandle, 0);
		AssertMsg( seekok != -1, "Error during seek" );

		assert(_fileSize > 0);
		_cbFileOffset = 0;
	}
}

//=============================================================================

DiskFileHD::~DiskFileHD()
{
	Validate();
	HALGetAssetAccessor().Close(_fileHandle);
}

//=============================================================================

void
DiskFileHD::SeekRandom( int32 position )
{
#if DO_HDUMP
#pragma message( "remove" )
	InitSimpleDisplay();
	char szMsg[ 80 ];
	sprintf( szMsg, "SeekRandom: pos=%ld sector=%d\n", position, position / DiskFileCD::_SECTOR_SIZE );
	FntPrint( szMsg );
	UpdateSimpleDisplay();
#endif
	Validate();
	AssertMsg(position >= 0,"position requested = " << position);
	assert(position <= _fileSize);
	AssertMsg( position % DiskFileCD::_SECTOR_SIZE == 0, "position = " << position );

	int64_t seekok = HALGetAssetAccessor().SeekAbsolute(
		_fileHandle, static_cast<int64_t>(_cbFileOffset + position) );
	AssertMsg( seekok != -1, "Error during seek" );

	_currentFilePosition = position;
	_hasSeeked = true;
}

//=============================================================================

void
HDump(char* title, void* buffer, ulong bufferSize);

void
DiskFileHD::ReadBytes( void* buffer, int32 size )
{
	assert(_hasSeeked == true);
	if(!_hasSeeked)
		FatalError(__FILE__ ": ReadBytes called without a seek");

#if DO_HDUMP
#pragma message( "remove" )
	InitSimpleDisplay();
	char szMsg[ 80 ];
	sprintf( szMsg, "ReadBytes: size=%ld, buffer = %p\n", size, buffer );
	FntPrint( szMsg );
	UpdateSimpleDisplay();
#endif
	Validate();
	assert(size > 0);
	assert(ValidPtr(buffer));
	AssertMsg( (_fileSize - _currentFilePosition) >= size, "_fileSize=" << _fileSize << ", _currentFilePosition=" << _currentFilePosition << ", size=" << size );
	assert(_currentFilePosition % DiskFileCD::_SECTOR_SIZE == 0);
	AssertMsg(size % DiskFileCD::_SECTOR_SIZE == 0, "size = " << size);

	int64_t cbRead = HALGetAssetAccessor().Read(_fileHandle, buffer, size);
	assert( cbRead == size );
	_currentFilePosition += size;
	_hasSeeked = false;

#if DO_HDUMP
	HDump("Sector Dump:",((char*)buffer)-36, size);
#endif
}

//=============================================================================
