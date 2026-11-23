# Chinese file names and game titles

The built-in fonts have no Chinese glyphs, so a folder or ROM named `超级马里奥.nds` would show
empty boxes. This fork can draw them with a font file on the SD card.

## Setup
Put `cjk.nft2` in `/_pico/fonts/` on the SD card. The release zip already has it in its `_pico`
folder, so copying that folder over the one on the card is enough. Nothing else needs to be
changed. Without the file the launcher looks exactly as before.

What changes with the font present:
- File and folder names with Chinese characters are drawn.
- A DS game or `.bnr` file that has a Chinese banner title shows it instead of the English one.
  Games without one keep the English title.
- The font only fills in characters the built-in fonts lack, so Latin letters, digits and kana look
  as before.

Loading the font takes about 0.5 MB of memory and a moment at startup.

## What the font covers
All of GB2312: the simplified Chinese characters, CJK punctuation and fullwidth forms. Traditional
characters outside it show as blank space. The glyphs are the 12 pixel WenQuanYi Bitmap Song,
see [the license](../licenses/wqy-bitmap-song.txt).

## Building the font yourself
CI builds it for every push. By hand, on Debian or Ubuntu:

```sh
sudo apt install python3 pcf2bdf xfonts-wqy
python3 tools/make_cjk_font.py --output cjk.nft2
```

`tools/make_cjk_font.py --check cjk.nft2` verifies a font file.

## Not translated yet
Menus, panels and the other interface text are still English.
