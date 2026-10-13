// SPDX-License-Identifier: GPL-3.0-only
#include "macho.hpp"
#include <iostream>
#include <stdexcept>
using compatlol::parse_macho;
void require(bool x){if(!x)throw std::runtime_error("test assertion failed");}
void put(std::vector<uint8_t>&b,size_t p,uint32_t n){for(int i=0;i<4;i++)b[p+i]=(n>>(i*8))&255;}
bool rejects(const std::vector<uint8_t>&b){try{parse_macho(b);return false;}catch(const std::exception&){return true;}}
int main(){try{std::vector<uint8_t>b(32);put(b,0,0xfeedfacf);put(b,4,0x01000007);require(parse_macho(b)[0]["arch"]=="x86_64");for(size_t n=0;n<32;n++)require(rejects(std::vector<uint8_t>(b.begin(),b.begin()+n)));put(b,4,0x0100000c);require(parse_macho(b)[0]["arch"]=="arm64");put(b,16,1);require(rejects(b));b.resize(40);put(b,20,8);put(b,32,0x1b);put(b,36,8);require(rejects(b));put(b,32,123);require(parse_macho(b)[0]["load_commands"][0]==123);put(b,36,0xffffffff);require(rejects(b));std::vector<uint8_t>fat={0xca,0xfe,0xba,0xbe,0xff,0xff,0xff,0xff};require(rejects(fat));for(unsigned n=0;n<1024;n++){std::vector<uint8_t>f(n%80, uint8_t(n));if(f.size()>=4)put(f,0,0xfeedfacf);try{parse_macho(f);}catch(const std::exception&){};}// Valid FAT big-endian table containing a little-endian x86-64 slice.
std::vector<uint8_t>universal(60);auto big=[&](size_t p,uint32_t v){for(size_t i=0;i<4;i++)universal[p+i]=(v>>(8*(3-i)))&255;};big(0,0xcafebabe);big(4,1);big(8,0x01000007);big(16,28);big(20,32);put(universal,28,0xfeedfacf);put(universal,32,0x01000007);require(parse_macho(universal)[0]["arch"]=="x86_64");big(16,4);require(rejects(universal));
// One valid dylib command, then malformed command-relative string offset.
std::vector<uint8_t>dylib(64);put(dylib,0,0xfeedfacf);put(dylib,4,0x01000007);put(dylib,16,1);put(dylib,20,32);put(dylib,32,0x80000018);put(dylib,36,32);put(dylib,40,24);dylib[56]='a';require(parse_macho(dylib)[0]["dylibs"][0]["weak"]==true);put(dylib,40,8);require(rejects(dylib));
std::cout<<"host-contracts: passed (synthetic Mach-O only)\n";return 0;}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
