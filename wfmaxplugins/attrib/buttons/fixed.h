#ifndef FIXED_H
#define FIXED_H

#include "../oaddlg.h"

class Fixed32 : public uiDialog
	{
public:
	Fixed32::Fixed32( typeDescriptor* td );
	virtual Fixed32::~Fixed32();

	virtual dataValidation copy_to_xdata( byte* & saveData );
	virtual int make_dialog_gadgets( HWND );
	void reset( byte* & );
	//virtual void composeHelp( char* entries[] );

	virtual int storedDataSize() const;

	virtual bool enable( bool bEnabled );
	virtual double eval() const;

protected:
	virtual void reset();
	void reset( char* );
	void reset( fixed32 );
	HWND hwndEdit;
	ICustEdit* _edit;
	HWND hwndSpinner;
	ISpinnerControl* _spinner;
	};

#endif
