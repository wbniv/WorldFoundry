// int.cpp

#include <cstdio>
#include <cstdlib>
#include <cstddef>
#include <pigsys/pigsys.hp>
#include <cstring>

#include "../util.hp"
#include <oas/oad.h>

#include "../oaddlg.hp"
#include <attrib/buttons/int.hp>

Int::Int( typeDescriptor* td ) : uiDialog( td )
{
	_bSave = true;
}


Int::~Int()
{
//	assert( _edit );
//	ReleaseICustEdit( _edit );

	//assert( _spinner );
	//ReleaseISpinner( _spinner );

	assert( hwndEdit );
	DestroyWindow( hwndEdit );

	//assert( hwndSpinner );
	//DestroyWindow( hwndSpinner );
}


void
Int::show_hide( int msgCode )
{
	uiDialog::show_hide( msgCode );
	assert( hwndEdit );
	ShowWindow( hwndEdit, msgCode );
}


int
Int::storedDataSize() const
{
	char szBuffer[ 128 ];
	assert( hwndEdit );
	Edit_GetText( hwndEdit, szBuffer, sizeof( szBuffer ) );

	return uiDialog::storedDataSize() + strlen( szBuffer ) + 1;
}


double
Int::eval() const
{
	assert( hwndEdit );
	char szBuffer[ 128 ];
	Edit_GetText( hwndEdit, szBuffer, sizeof( szBuffer ) );
	return atof( szBuffer );
}


bool
Int::enable( bool bEnabled )
{
	if ( uiDialog::enable( bEnabled ) )
	{
		assert( hwndEdit );
		Edit_Enable( hwndEdit, uiDialog::enable() );
		return true;
	}
	else
		return false;
}


int
Int::make_dialog_gadgets( HWND hPanel )
{
	int x;
	int width;

	assert( _td );

	assert( hPanel );
	assert( hInstance );
	assert( _td->name );

	int wLabel = uiDialog::make_dialog_gadgets( hPanel );

	x = 5 + wLabel;
	width = min( LAST_BUTTON_WIDTH( x ), 50 );
	hwndEdit = theAttributes->CreateWindowEx(
		0,
//		"CustEdit",
		"EDIT",
		_td->name,
		0 | WS_TABSTOP,
		x,
		theAttributes->y,
		width, 16,
		hPanel,
		NULL,
		hInstance,
		NULL );
	assert( hwndEdit );
	Button_SetFont( hwndEdit, theAttributes->_font );
//	_edit = GetICustEdit( hwndEdit );
//	assert( _edit );

#if 0
	hwndSpinner = theAttributes.CreateWindowEx(
		0,
		"SpinnerControl",
		"",
		0,
		x + width + 1,
		y,
		7,
		10,
		hPanel,
		NULL,
		hInstance,
		NULL );
	assert( hwndSpinner );
	_spinner = GetISpinner( hwndSpinner );
	assert( _spinner );
#endif

	reset();

//	_spinner->LinkToEdit( hwndEdit, EDITTYPE_INT );
//	_spinner->SetAutoScale();

	return x + width + 1 + 7;
}


///////////////////////////////////////////////////////////////////////////////

dataValidation
Int::copy_to_xdata( byte* & saveData )
{
//	int i;

	assert( _td );

	assert( hwndEdit );
	char szBuffer[ 128 ];
	Edit_GetText( hwndEdit, szBuffer, sizeof( szBuffer ) );
#if 0
	expressionBuffer = szBuffer;
	int parseError = yyparse();
	if ( parseError != 0 )
	{
		MessageBox( NULL, fieldName(), "Error in expression", MB_OK );
		i = 0;
	}
	else
		i = long( expressionParserValue );
#endif

	uiDialog::copy_to_xdata( saveData );
	strcpy( (char*)saveData, szBuffer );
	saveData += strlen( (char*)saveData ) + 1;

	return DATA_OK;
}


void
Int::reset()
{
	assert( _td );
	reset( _td->def );
}


void
Int::reset( long data )
{
	assert( _td );

//	if ( !( _td->min <= data && data <= _td->max ) )
//		debug( "Invalid range for %s %d:[%d..%d]",
//			_td->name, _td->def, _td->min, _td->max );
//	assert( _td->min <= data && data <= _td->max );

	assert( hwndEdit );
	char szBuffer[ 256 ];
	sprintf( szBuffer, "%ld", data );
	Edit_SetText( hwndEdit, szBuffer );
//	_edit->SetText( data );

#if 0
	assert( _spinner );
	_spinner->SetLimits( _td->min, _td->max );
	_spinner->SetResetValue( _td->def );
	_spinner->SetValue( data, FALSE );
#endif
}


void
Int::reset( char* data )
{
	assert( hwndEdit );
	Edit_SetText( hwndEdit, data );
}


void
Int::reset( byte* & saveData )
{
	_bUserOverrideEnable = true;
	byte* pSaveData = saveData;
	reset( (char*)pSaveData );
	saveData += strlen( (char*)pSaveData ) + 1;
}

///////////////////////////////////////////////////////////////////////////////

Int32::Int32( typeDescriptor* td ) : Int( td )
{
}
