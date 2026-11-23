#include "common.h"
#include <stdlib.h>
#include <malloc.h>
#include <string.h>
#include "fat/File.h"
#include "nitroFont2.h"
#include "FallbackFont.h"

// the nft2 header is 20 bytes, followed by the glyph table, the char map and the glyph data
#define NFT2_HEADER_SIZE    20
#define MAX_FONT_SIZE       (2 * 1024 * 1024)

bool fallbackFont_load(const char* path)
{
    File file;
    if (file.Open(path, FA_READ | FA_OPEN_EXISTING) != FR_OK)
    {
        return false;
    }

    u32 size = file.GetSize();
    if (size < NFT2_HEADER_SIZE || size > MAX_FONT_SIZE)
    {
        return false;
    }

    // the glyph tables are read as 32 bit values, so the data needs to be aligned
    void* data = memalign(32, (size + 31) & ~31);
    if (!data)
    {
        LOG_DEBUG("Not enough memory for the fallback font\n");
        return false;
    }

    if (!file.ReadExact(data, size))
    {
        free(data);
        return false;
    }

    nft2_header_t* font = (nft2_header_t*)data;
    // the pointers in the header are still offsets until the font is unpacked
    if (font->signature != NFT2_SIGNATURE
        || (u32)font->glyphInfoPtr >= size
        || (u32)font->charMapPtr >= size
        || (u32)font->glyphDataPtr >= size
        || font->glyphCount == 0
        || (u32)font->glyphInfoPtr + font->glyphCount * sizeof(nft2_glyph_t) > size)
    {
        free(data);
        return false;
    }

    if (!nft2_unpack(font))
    {
        free(data);
        return false;
    }

    nft2_setFallbackFont(font);
    LOG_DEBUG("Loaded the fallback font (%u glyphs)\n", font->glyphCount);
    return true;
}
