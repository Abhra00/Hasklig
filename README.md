# Hasklig

Hasklig is a monospaced code font with ligatures, forked from
[Source Code Pro](http://adobe-fonts.github.io/source-code-pro/) and merging in
the ligature work originally designed by [Ian Tuomi](https://github.com/i-tu/Hasklig).

This fork re-applies Hasklig's ligature set onto Source Code Pro's current
upstream glyphs, since the original [i-tu/Hasklig](https://github.com/i-tu/Hasklig)
project is archived and no longer tracks new Source Code Pro releases.

## Getting involved

[Open an issue](../../issues) or send a pull request if you find a bug or want
to suggest an improvement.

## Releases

* [Latest release](../../releases/latest)
* [All releases](../../releases)

## Building the fonts from source

### Requirements

To build the binary font files from source, you need Python 3 along with the
[Adobe Font Development Kit for OpenType](https://github.com/adobe-type-tools/afdko/) (AFDKO) and
[FontTools](https://github.com/fonttools/fonttools) packages, which you can install with

```sh
pip3 install afdko
```

### Building one font

The key to building the OTF fonts is `makeotf`, which is part of the AFDKO toolset.
Information and usage instructions can be found by executing `makeotf -h`. The TTFs
are generated with the `otf2ttf` and `ttfcomponentizer` tools.

Commands to build the Regular style OTF font:

```sh
cd Upright/Instances/Regular/
makeotf -r -gs -omitMacNames
```

Commands to generate the Regular style TTF font:

```sh
otf2ttf Hasklig-Regular.otf
ttfcomponentizer Hasklig-Regular.ttf
```

### Building all fonts

For convenience, a shell script named **build.sh** is provided in the root directory.
It builds all OTFs and TTFs into a directory called **target/**. It can be executed by typing:

```sh
./build.sh
```

or this on Windows:

```sh
build.cmd
```
