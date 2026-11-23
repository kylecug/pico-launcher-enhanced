#pragma once

/// @brief Loads the CJK fallback font from the SD card and registers it with
///        \see nft2_setFallbackFont, so Chinese file names and game titles
///        can be drawn although the built-in fonts have no such glyphs.
///        The font is optional: without the file everything looks as before.
/// @param path The path of the .nft2 font file.
/// @return True if the font was loaded, or false otherwise.
bool fallbackFont_load(const char* path);
