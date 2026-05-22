//==============================================================================
// lmalloc.cc
// Copyright ( c ) 1997,1998,1999,2000,2001,2003 World Foundry Group.  
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
// Description:
// Sequential memory allocation class, usefull for temporary buffers which
// last a frame or so.
//============================================================================

#define _LMALLOC_CC
#include <memory/lmalloc.hp>
#include <cpplib/align.hp>
#include <cstdint>
#include <cpplib/stdstrm.hp>
#include <streams/dbstrm.hp>
#include <cpplib/libstrm.hp>
#include <hal/hal.h>

#define LMALLOC_TRACK_SIZE 1
#define LMALLOC_TRACK_LINE_AND_FILE 0

#if LMALLOC_TRACK_LINE_AND_FILE
#if !MEMORY_TRACK_FILE_LINE
#error LMALLOC_TRACK_LINE_AND_FILE wont work without MEMORY_TRACK_FILE_LINE set
#endif
#endif

//=============================================================================

#if DO_ASSERTIONS
#if LMALLOC_TRACK_SIZE

struct FileLine
{
	enum
	{
		ALLOCATED = 'ALOC',
		FREED = 'FREE',
		CANARY_VALUE = (int32)0xDEADBEEF
	};
	int32 _state;
	int _size;			                // size of allocation (includes FileLine header + canary)
#if LMALLOC_TRACK_LINE_AND_FILE
	char* _file;						// file and line allocation occured on
	int _line;
#endif
	// On 64-bit, sizeof(FileLine)+sizeof(int32 canary)=12, not a multiple of 8.
	// This pad makes overhead 16 bytes (2×8), eliminating false-positive alignment
	// warnings for correctly-aligned user allocations.  No-op on 32-bit (SIZE_MAX≤4G).
#if SIZE_MAX > 0xFFFFFFFFUL
	int32 _pad;
#endif
};
#endif

//==============================================================================

void
LMalloc::_Validate() const
{
	Memory::Validate();

	assert(ValidPtr(_memory));
	assert(ValidPtr((_endMemory-4)));
	AssertMsg(ValidPtr(_currentFree),"currentFree = " << _currentFree);
	assert(_currentFree >= _memory);
	assert(_currentFree < (_endMemory));
	assert(_flags == 0 || _flags == FLAG_MEMORY_OWNED);

#if LMALLOC_TRACK_SIZE
	char* p = _memory;
	while (p < _currentFree)
	{
		FileLine* fl = (FileLine*)p;
		AssertMsg(fl->_state == FileLine::ALLOCATED, "LMalloc _Validate: block not ALLOCATED at " << (void*)p);
		AssertMsg(*(int32*)((char*)fl + fl->_size - sizeof(int32)) == FileLine::CANARY_VALUE,
		          "LMalloc _Validate: canary corrupted at " << (void*)p);
		p += fl->_size;
	}
#endif
}

#endif // DO_ASSERTIONS

//=============================================================================

#if DO_IOSTREAMS
std::ostream&
LMalloc::_Print(std::ostream& out) const
{
	out << "LMalloc Dump: [named " << Name() << ']' << std::endl;
	out << "_flags = " << _flags << std::endl;
	out << "_memory = " << (void*)_memory << std::endl;
	out << "_endMemory = " << (void*)_endMemory << std::endl;
	out << "_currentFree = " << (void*)_currentFree << std::endl;
	out << "_parentMemory = " << (void*)_parentMemory << std::endl;
	int cbUsed = _currentFree - _memory;
	int cbFree = _endMemory - _currentFree;
	int cbTotal = _endMemory - _memory;
	//assert( cbUsed + cbFree == cbTotal );
	out << cbUsed << '/' << cbTotal << " free=" << cbFree << std::endl;
	return out;
}

#endif

//=============================================================================

LMalloc::LMalloc(LMalloc& lmalloc, size_t size MEMORY_NAMED ( COMMA const char* name ) )
	: Memory( MEMORY_NAMED( name ) )
	// allocates from another lmalloc memory pool
{
	RangeCheckExclusive(0,size,1000000);  // kts arbitrary
	lmalloc.Validate();
	_memory = (char*)lmalloc.Allocate(size ASSERTIONS( COMMA __FILE__ COMMA __LINE__ ));
	assert(ValidPtr(_memory));
	AssertMemoryAllocation(_memory);
	//DBSTREAM1( printf("LMalloc::LMalloc: allocated %d bytes from lmalloc at address %p\n",size,_memory); )
	//printf("New LMalloc ");
	//MEMORY_NAMED( printf("named %s ",name); )
	//printf(" allocated %d bytes from lmalloc ",size);
	//MEMORY_NAMED( printf(" named %s ",lmalloc._name); )
	//printf(" at address %p\n",_memory);
	_endMemory = _memory + size;
	_currentFree = _memory;
	_flags = FLAG_MEMORY_OWNED;
	_parentMemory = &lmalloc;
	assert(ValidPtr(_parentMemory));
	Validate();
}

//=============================================================================

#if 0
LMalloc::LMalloc(size_t size MEMORY_NAMED( COMMA const char* name ) )
{
	assert(size);
	_memory = (char*)malloc(size);
	assert(ValidPtr(_memory));
	AssertMemoryAllocation(_memory);
	_endMemory = _memory + size;
	_currentFree = _memory;
	_flags = FLAG_MEMORY_OWNED;
	_parentMemory = NULL;
	MEMORY_NAMED( ValidatePtr(name);
		_name = name;
	)
	Validate();
	//DBSTREAM1( printf("LMalloc::LMaloc constructed from heap at address %p with a size of %d\n",_memory,size); )
	//printf("LMalloc ");
	//MEMORY_NAMED( printf(" named %s ",name); )
	//printf("constructed from heap at addr %p, size = %d\n",_memory,size);
}
#endif

//=============================================================================

LMalloc::LMalloc(void* memory, size_t size MEMORY_NAMED( COMMA const char* name ) )
	: Memory( MEMORY_NAMED( name ) )
{
	assert(size);
	assert(size >= 4);
	AssertMsg(ValidPtr(memory),"memory = " << memory);
	AssertMsg(((uintptr_t)memory & WF_POINTER_ALIGN_MASK) == 0, "LMalloc base pointer must be " << WF_POINTER_ALIGN << "-byte aligned, got " << memory);
	_memory = (char*)memory;
	assert(ValidPtr(_memory));
	_endMemory = _memory + size;
	assert(ValidPtr(_endMemory-4));
	_currentFree = _memory;
	_flags = 0;
	_parentMemory = NULL;
	Validate();
	//DBSTREAM1( printf("LMalloc::LMaloc constructed from pointer at address %p with a size of %d\n",_memory,size); )
	//printf("Lmalloc ");
	//MEMORY_NAMED( printf(" named %s ",_name); )
	//printf(" constructed from ptr at addr %p, size = %d\n",_memory,size);
}

//=============================================================================

LMalloc::~LMalloc()
{
#pragma message( "spew `DEL' tracking messages for all allocations" )
	Validate();
	if(_flags & FLAG_MEMORY_OWNED)
	{
		if(_parentMemory)
			_parentMemory->Free(_memory);
//		else
//			free(_memory);
	}
}

//=============================================================================

void*
LMalloc::Allocate(size_t size ASSERTIONS( COMMA const char* file COMMA int line))
{
	Validate();
	assert(size);

	DBSTREAM1( cmem << "NEW," << size << ','; )

#if DO_ASSERTIONS
#if LMALLOC_TRACK_SIZE
	size += sizeof(FileLine);
	size += sizeof(int32);		// canary sentinel
#endif
#endif

	if(size & WF_POINTER_ALIGN_MASK)
	{
		DBSTREAM1(cwarn << "LMalloc of " << size << " not " << WF_POINTER_ALIGN << "-byte aligned, rounding up" << std::endl; )
	}
	size = ALIGN_POW2(size, WF_POINTER_ALIGN);
	assert(ValidPtr(_memory+size));			// insure the size is ok for this architecture

	if((_currentFree + size) >= (_endMemory))
	{
		char errorBuffer[400];

		sprintf(errorBuffer, "Lmalloc based at address %p out of memory, request size = %d. lmalloc remaining = %d\n",_memory, size,_endMemory-_currentFree);
		MEMORY_NAMED ( sprintf(errorBuffer, "Lmalloc based at address %p out of memory, request size = %d. lmalloc remaining = %d, Named %s\n",_memory, size,_endMemory-_currentFree,_name); )
		DBSTREAM1( cerror << *this << std::endl; )
		AssertMsg(0,errorBuffer);
		FatalError(errorBuffer);
		//FatalError("Lmalloc out of memory");
		return(0);                      					// hope somebody notices
	}
	assert((_currentFree + size) < (_endMemory));		// if this fires, we are out of memory

	void* retVal = _currentFree;
	_currentFree += size;
#if DO_ASSERTIONS
#if LMALLOC_TRACK_SIZE
	if ((char*)retVal > _memory)
		AssertMsg(*(int32*)((char*)retVal - sizeof(int32)) == FileLine::CANARY_VALUE,
		          "LMalloc: canary corrupted — buffer overrun in previous allocation");
	FileLine* fl = (FileLine*)retVal;
	fl->_state = FileLine::ALLOCATED;
#if LMALLOC_TRACK_LINE_AND_FILE
	fl->_file = file;
	fl->_line = line;
#endif		// LMALLOC_TRACK_LINE_AND_FILE
	fl->_size = size;
	*(int32*)((char*)retVal + size - sizeof(int32)) = FileLine::CANARY_VALUE;
	retVal = ((char*)retVal) + sizeof(FileLine);
#endif		// LMALLOC_TRACK_SIZE
#endif		// DO_ASSERTIONS

	ASSERTIONS( DBSTREAM1( cmem << size << ',' << file << ',' << line << "," << retVal << "," << Name() << std::endl; ) )

//	printf("memory allocated from lmalloc ");
//	DBSTREAM1( printf(" named %s ",_name); )
//	printf(" at %p,size = %d, left = %d\n",retVal, size, _endMemory-_currentFree);
	return(retVal);
}

//============================================================================

#define DUMPDATA

void
LMalloc::Free(const void* mem)
{
	Validate();

//	NEW|DEL, size, rounded_size, file, line, index, address, comments
//	cmem << "DEL," << 0 << ',' << 0 << ',' << "filename" << ",0," << mem << ',' << Name() << std::endl;
	DBSTREAM1( cmem << "DEL," << mem << ',' << Name() << std::endl; )

#if DO_ASSERTIONS
#if LMALLOC_TRACK_SIZE
	mem = ((char*)mem) - sizeof(FileLine);
#endif
#endif
	assert(ValidPtr(mem));
	AssertMsg(mem >= _memory, "mem = " << (void*)mem << ", _memory = " << _memory << "(Probably freed from wrong Memory instance");
	assert(mem < (_endMemory));

#if DO_ASSERTIONS
#if LMALLOC_TRACK_SIZE
	FileLine* fl = (FileLine*)mem;
	AssertMsg(*(int32*)((char*)mem + fl->_size - sizeof(int32)) == FileLine::CANARY_VALUE,
	          "LMalloc: canary corrupted at Free — buffer overrun detected");
	assert(fl->_state == FileLine::ALLOCATED);

	FileLine* nextfl = (FileLine*)(((char*)mem)+fl->_size);
	if(!(nextfl->_state == FileLine::ALLOCATED))
		nextfl = NULL;

	if(nextfl)
	{
		cerror << "LMalloc allocation mismatch:" << std::endl;
		// Enumerate every still-allocated block sitting on top of the block
		// we're trying to free, so the LIFO-violating allocations can be
		// identified by size (with -lms to see file:line for those sizes).
		// Added 2026-05-18 while hunting the UnloadLevel LIFO chain; kept
		// because the diagnosis trail in docs/investigations/2026-05-18-
		// unloadlevel-lifo-bug.md depends on it for follow-up bugs in
		// WFGame::~WFGame and engine shutdown.
		cerror << "  trying to free block: addr=" << (void*)mem
		       << " size=" << fl->_size << std::endl;
		cerror << "  blocks still allocated on top (in stack-top → bottom order):" << std::endl;
		FileLine* walk = nextfl;
		int idx = 0;
		while (walk && walk->_state == FileLine::ALLOCATED && (char*)walk < _currentFree) {
			cerror << "    [" << idx << "] addr=" << (void*)walk
			       << " size=" << walk->_size << std::endl;
			walk = (FileLine*)(((char*)walk) + walk->_size);
			if (++idx > 20) { cerror << "    ... (truncated)" << std::endl; break; }
		}
		cerror << "  _currentFree=" << (void*)_currentFree
		       << "  expected mem=" << (void*)(_currentFree - fl->_size) << std::endl;
#if LMALLOC_TRACK_LINE_AND_FILE
		cerror << "should have freed: file = " << fl->_file << ", line = " << fl->_line << std::endl;
		cerror << "but tried to free: file = " << nextfl->_file << ", line = " << nextfl->_line << std::endl;
#endif			// LMALLOC_TRACK_LINE_AND_FILE
	}
	assert((_currentFree - fl->_size) == mem);
#endif			// LMALLOC_TRACK_SIZE
#endif			// DO_ASSERTIONS
//	AssertMsg((_currentFree - size) == mem, "_currentFree = " << (void*)_currentFree << ", size = " << size << ", mem  = " << mem ASSERTIONS( << ", file = " << fl->_file << ", line = " << fl->_line));			// can only free last allocated

   RangeCheck(_memory,mem,_endMemory);
   //assert(mem <= _currentFree);
	_currentFree = (char*)mem;
#if DO_ASSERTIONS
#if LMALLOC_TRACK_SIZE
	fl->_state = FileLine::FREED;
#endif
#endif
}

//=============================================================================
