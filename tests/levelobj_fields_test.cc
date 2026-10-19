// Level Object payload decoder probe for tests/test_levelobj_fields.py.
//
//   levelobj_fields_test layout
//       prints the offset of PrewarmNoPaletteProgram and sizeof(_LevelObj)
//   levelobj_fields_test decode PAYLOAD
//       reads a Level Object OAD payload (exactly its on-disk OADSize bytes)
//       into an allocation of exactly that size and prints the decoded value
//   levelobj_fields_test unchecked PAYLOAD
//       reads the field without the payload-length check: the negative
//       control. Under AddressSanitizer an old (shorter) payload must abort
//       with heap-buffer-overflow, proving the probe can see an over-read.
#include <game/levelobj_fields.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

int main(int argc, char** argv)
{
	if (argc == 2 && !std::strcmp(argv[1], "layout"))
	{
		std::printf("offset=%zu size=%zu\n", offsetof(_LevelObj, PrewarmNoPaletteProgram), sizeof(_LevelObj));
		return 0;
	}
	if (argc != 3) { std::fprintf(stderr, "usage: %s layout | decode|unchecked PAYLOAD\n", argv[0]); return 2; }
	FILE* f = std::fopen(argv[2], "rb");
	if (!f) { std::perror(argv[2]); return 2; }
	std::vector<char> bytes;
	for (int c; (c = std::fgetc(f)) != EOF;) bytes.push_back(char(c));
	std::fclose(f);
	// Exactly the payload's length, so any read past it is a heap overflow.
	char* payload = static_cast<char*>(std::malloc(bytes.size()));
	std::memcpy(payload, bytes.data(), bytes.size());
	const _LevelObj* oad = reinterpret_cast<const _LevelObj*>(payload);
	int value;
	if (!std::strcmp(argv[1], "decode"))
		value = LevelObjPrewarmNoPaletteProgram(oad, int(bytes.size())) ? 1 : 0;
	else if (!std::strcmp(argv[1], "unchecked"))
		value = oad->PrewarmNoPaletteProgram != 0;
	else
		return 2;
	std::printf("payload-bytes=%zu prewarm=%d\n", bytes.size(), value);
	std::free(payload);
	return 0;
}
