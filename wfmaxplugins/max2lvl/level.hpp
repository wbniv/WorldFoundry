//============================================================================
// level.hp:
// Copyright(c) 1995 Cave Logic Studios / PF.Magic
//============================================================================
/* Documentation:

	Abstract:
			3D Game level format in memory
	History:
			Created	05-04-95 11:08am Kevin T. Seghetti

	Class Hierarchy:
			none

	Dependancies:
		PIGS, BRender, STDIO
*/
//============================================================================

// use only once insurance
#ifndef _lEVEL_HP
#define _lEVEL_HP

//============================================================================

#include "global.hpp"

#include <stl/vector.h>
#include <stl/map.h>
#include <stl/bstring.h>

#include "asset.hpp"
#include "object.hpp"
#include "model.hpp"
#include "path.hpp"
#include "room.hpp"
#include "oad.hpp"
#include "ptrobj.hpp"
#include "channel.hpp"

class QFile3ds;

//============================================================================

// used to insure all output is long word aligned
#define ALIGNED(a) (!(a & 3))


#define MAXCOMMONSIZE (64*1024)     // max in-memory size of common block area
#define MAXBLOCKSIZE 256			// max size of a single common block
#define OADBUFFER_SIZE 60000

//============================================================================

#if 0
struct
mergedObject
{
	string modelName;
	Matrix3 _mat;
};
#endif

//============================================================================
// in memory representation of a level

class QLevel
{
public:
	QLevel(const char* levelFileName, const char* lcFileName /*, SceneEnumProc* theScene*/ );
	~QLevel();
	void DoCrossReferences(const string& inputFileName, const string& lcFileName, const string& outputFileName);							// handle references, and cameras etc.

	void Save(const char* name);				// write out entire level structure, ready to load into the game

	void PrintNameList( ostream& out) const;
	int16 GetObjectIndex(const QObject* object) const;	// return index of object in array, used to create other object lists, which refer to this one
	int FindObjectIndex(const string& name) const;		// look up object based on name
	void PrintObjectList(ostream& output) const;
	const QObject& GetObject(int index) const { return objects[index]; }
	const QRoom& GetRoom(int idxRoom) const { return rooms[idxRoom]; }
	int GetObjectCount() const { return objects.size(); }
	int GetRoomCount() const { return rooms.size(); }
	const QPath& GetPath(int index) const { return paths[index]; }
	int16 NewChannel(void);
	Channel& GetChannel(int index) { return channels[index]; }
	QObjectAttributeData GetOAD(int index) const { return(objectOADs[index]); }
	int32 GetClassIndex(const string& name) const;
	packedAssetID FindAssetID(int roomNum, const string& name);


private:
	QLevel();											// prevent construction without parameters
	void ResolvePathOffsets() const;
	void LoadLCFile(const char* lcFileName);			// load LevelCon file from .oas directory
	void LoadAssetFile(const char* lcFileName);			// load assets.txt from the .oad directory
	void LoadOADFiles(const char* pathName);			// load all .oad files from the .oad directory
	void SaveLVLFile(const char* name);					// write out the .lvl file
	void CreateAssetLST(const char* name);				// fill allAssets vector with asset IDs
	asset AssignUniqueAssetID(const char* name, unsigned int roomNum);	// Generate unique id for this filename
	void PatchAssetIDsIntoOADs();						// backpatch OADs with assetIDs
	void SaveLSTFile(const char* name);					// write out .lst file containing list of assets used in this level
	void SaveAssetLSTFile(const char* name);			// write out asset.lst file containing list of assets used in this level
//	void CreateScarecrowFiles(string inputFileName, string lcFileName, string outputFileName);
	void CreateQObjectList(/*SceneEnumProc* theSceneEnum*/);	// This replaces Load3DStudio()
	void CreateQObjectFromSceneNode(Mesh* thisMesh, INode* thisNode, TimeValue theTime);		// This replaces Get3DStudioMesh()

	void CompileScripts(const string& inputFileName, const string& lcFileName);		// go through all objects and compile any AI scripts
	void SortIntoRooms();								// go through all objects with 3d coordindates and place them into rooms
//	void CreateMergedObjects(const string& templatename);				// merged all statplats in a room into one large merged object
	void CreateCommonData();	// walk objects and create common data area, and offsets into it
	void AddXDataToCommonData();
	int32 AddCommonBlockData(const void* data, int32 size);	// add some data to the common block, and return its offset
	void SortCameraBoxes();								// sort actboxca objects by nesting order
	bool ValidateVelocityLevel() const;					// Do Velocity-specific consistancy checks on the level

	int32 ParseTextFileIntoObjectList(char* textBuffer, int32 sourceSize, long* objectReferenceArray,int32 maxEntries);
	int32 ParseTextFileIntoContextualAnimationList(char* textBuffer,
												   int32 sourceSize,
												   long contextAnimationArray[][2],
												   int32 maxEntries,
												   int32 roomNum);

	void StripLeadingPath(char* oldFilename);

// these arrays are loaded from disk
	vector<string> objectTypes;						// array of strings containing the object type names
	vector<QObjectAttributeData> objectOADs;			// array of OAD's by type

// these arrays are created from above data at run time
	vector< PtrObj<QObject> > objects;					// array of pointers to objects
	vector<QPath> paths;								// array of pointers to QPath, generated from the objects
	vector<Channel> channels;							// array of pointers to uncompressed channels
	vector<QRoom> rooms;								// array of rooms containing object pointers
//	vector<vector<mergedObject> > allMergedObjects;		// array of arrays of mergedObjects [room][object]
	vector<vector<asset> > allAssets;					// array of arrays of assetIDs [room][asset]

// common block storage
	int32 commonAreaSize;
	char commonArea[MAXCOMMONSIZE];

// asset filename extension database
	AssetExtensions assetExts;

	vector<vector<int> > assetIndices;			// array of arrays of current indices for each asset type [room][type]

	map<string,string,less<string> > extensionsMap;
	vector<string> meshDirectories;

	TimeValue theTime;
};

//============================================================================

// keep this is sync with oas: mesh.inc, and the same enum in velsrc: actor.hp
enum
{
	MODEL_TYPE_BOX=0,
	MODEL_TYPE_MESH,
	MODEL_TYPE_SCARECROW,
	MODEL_TYPE_NONE,
	MODEL_TYPE_LIGHT,
	MODEL_TYPE_MATTE,
	MODEL_TYPE_MAX
};

#endif
//============================================================================
