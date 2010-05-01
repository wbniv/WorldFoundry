// fileline.hpp
#ifndef FILELINE_HPP
#define FILELINE_HPP

#include <pigsys/pigsys.hp>
#include <stdlib.h>
#include <pigsys/assert.hp>

struct yy_buffer_state;

class FileLineInfo
{
public:
	FileLineInfo(
		int nLine,
		const char* szLine,
		const char* szFilename,
		struct yy_buffer_state*
		);
	~FileLineInfo();

	char szFilename[ PATH_MAX ];
//	char szLine[ 512 ];
	char* szLine;
	int nLine;
	struct yy_buffer_state* yy_current_buffer;
//	char _szCurrentLine[ 512 ];
	char* _szCurrentLine;

private:
	FileLineInfo()		{ /* for STL */ }
};

#endif	// FILELINE_HPP