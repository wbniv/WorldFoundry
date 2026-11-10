// Level Object payload decoder probe for tests/test_levelobj_fields.py and the
// levelobj_short_record ctest.
//
//   levelobj_fields_test layout
//       prints the offsets of the appended fields and sizeof(_LevelObj)
//   levelobj_fields_test decode PAYLOAD
//       reads a Level Object OAD payload (exactly its on-disk OADSize bytes)
//       into an allocation of exactly that size and prints the decoded values
//   levelobj_fields_test unchecked PAYLOAD
//   levelobj_fields_test unchecked-editable PAYLOAD
//       read PrewarmNoPaletteProgram / EditableObjects without the
//       payload-length check: the negative controls. Under AddressSanitizer a
//       payload that predates the field must abort with heap-buffer-overflow,
//       proving the probe can see an over-read.
//   levelobj_fields_test level LEVEL.lvl
//       finds the level's Level Object, copies exactly its payload and decodes
//       it as `decode` does
#include <game/levelobj_fields.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static const int kLevelObjKind = 15;   // Actor::LevelObj_KIND, objects.e order
static const int kObjHeader = 68;      // sizeof(_ObjectOnDisk); OADSize is the int16 at 66

static bool
readFile(const char* path, std::vector<char>& bytes)
{
	FILE* f = std::fopen(path, "rb");
	if (!f) { std::perror(path); return false; }
	for (int c; (c = std::fgetc(f)) != EOF;) bytes.push_back(char(c));
	std::fclose(f);
	return true;
}

template <typename T> static T
at(const std::vector<char>& b, size_t offset)
{
	T v;
	std::memcpy(&v, b.data() + offset, sizeof v);
	return v;
}

// The first Level Object's payload, exactly OADSize bytes long.
static bool
levelObjectPayload(const std::vector<char>& lvl, std::vector<char>& payload)
{
	const int count = at<int32_t>(lvl, 4), objects = at<int32_t>(lvl, 8);
	for (int i = 0; i < count; ++i)
	{
		const int offset = at<int32_t>(lvl, objects + 4 * i);
		if (at<int16_t>(lvl, offset) != kLevelObjKind) continue;
		const int size = at<int16_t>(lvl, offset + 66);
		payload.assign(lvl.begin() + offset + kObjHeader, lvl.begin() + offset + kObjHeader + size);
		return true;
	}
	return false;
}

int main(int argc, char** argv)
{
	if (argc == 2 && !std::strcmp(argv[1], "layout"))
	{
		std::printf("prewarm=%zu editable=%zu labels=%zu types=%zu size=%zu\n",
		            offsetof(_LevelObj, PrewarmNoPaletteProgram), offsetof(_LevelObj, EditableObjects),
		            offsetof(_LevelObj, EditableObjectLabels), offsetof(_LevelObj, EditableTypeDescriptors),
		            sizeof(_LevelObj));
		return 0;
	}
	if (argc != 3) { std::fprintf(stderr, "usage: %s layout | decode|unchecked|unchecked-editable PAYLOAD | level LVL\n", argv[0]); return 2; }
	std::vector<char> bytes;
	if (!readFile(argv[2], bytes)) return 2;
	const char* mode = argv[1];
	if (!std::strcmp(mode, "level"))
	{
		std::vector<char> payload;
		if (!levelObjectPayload(bytes, payload)) { std::fprintf(stderr, "%s: no Level Object\n", argv[2]); return 1; }
		bytes.swap(payload);
		mode = "decode";
	}
	// Exactly the payload's length, so any read past it is a heap overflow.
	char* payload = static_cast<char*>(std::malloc(bytes.size()));
	std::memcpy(payload, bytes.data(), bytes.size());
	const _LevelObj* oad = reinterpret_cast<const _LevelObj*>(payload);
	const int size = int(bytes.size());
	if (!std::strcmp(mode, "decode"))
		std::printf("payload-bytes=%d prewarm=%d editable=%d labels=%d types=%d has-editable=%d\n", size,
		            LevelObjPrewarmNoPaletteProgram(oad, size) ? 1 : 0,
		            int(LevelObjEditableObjectsOffset(oad, size)),
		            int(LevelObjEditableObjectLabelsOffset(oad, size)),
		            int(LevelObjEditableTypeDescriptorsOffset(oad, size)),
		            LevelObjHasEditableObjects(oad, size) ? 1 : 0);
	else if (!std::strcmp(mode, "unchecked"))
		std::printf("payload-bytes=%d prewarm=%d\n", size, oad->PrewarmNoPaletteProgram != 0);
	else if (!std::strcmp(mode, "unchecked-editable"))
		std::printf("payload-bytes=%d editable=%d\n", size, int(oad->EditableObjects));
	else
		return 2;
	std::free(payload);
	return 0;
}
