// SPDX-License-Identifier: GPL-3.0-only
#include "macho.hpp"
#include <stdexcept>
#include <iomanip>
#include <sstream>
namespace compatlol {
namespace {
struct Reader {
 const std::vector<uint8_t>& b; size_t base, length; bool big;
 void bounds(size_t p,size_t n) const {if(p>length||n>length-p) throw std::runtime_error("MACHO_TRUNCATED");}
 uint64_t number(size_t p,size_t n) const {bounds(p,n);uint64_t v=0;for(size_t i=0;i<n;i++)v|=uint64_t(b[base+p+i])<<(8*(big?n-1-i:i));return v;}
 std::string text(size_t p,size_t end) const {bounds(p,end-p);std::string s;while(p<end){char c=char(b[base+p++]);if(!c)return s;s+=c;}throw std::runtime_error("MACHO_STRING_UNTERMINATED");}
};
std::string arch(uint32_t c){if(c==0x01000007)return "x86_64";if(c==0x0100000c)return "arm64";if(c==7)return "i386";return "unknown";}
Json thin(Reader r){auto m=r.number(0,4); bool is64=m==0xfeedfacf; if(!is64&&m!=0xfeedface)throw std::runtime_error("MACHO_BAD_MAGIC");size_t header=is64?32:28;r.bounds(0,header);auto count=r.number(16,4), size=r.number(20,4);r.bounds(header,size);if(count>size/8)throw std::runtime_error("MACHO_BAD_COMMAND_COUNT");Json out={{"arch",arch(r.number(4,4))},{"uuid",nullptr},{"min_os",nullptr},{"dylibs",Json::array()},{"rpaths",Json::array()},{"imports",Json::array()},{"load_commands",Json::array()},{"objc_metadata","not-inspected"}};size_t p=header,end=header+size;
 for(size_t i=0;i<count;i++){r.bounds(p,8);auto cmd=r.number(p,4),n=r.number(p+4,4);if(n<8||n>end-p)throw std::runtime_error("MACHO_BAD_COMMAND_SIZE");out["load_commands"].push_back(cmd);
 if(cmd==0x1b){if(n<24)throw std::runtime_error("MACHO_BAD_UUID");std::ostringstream s;for(size_t j=0;j<16;j++)s<<std::hex<<std::setfill('0')<<std::setw(2)<<r.number(p+8+j,1);out["uuid"]=s.str();}
 if(cmd==0xc||cmd==0x80000018||cmd==0x8000001f||cmd==0x80000023){if(n<24)throw std::runtime_error("MACHO_BAD_DYLIB");auto o=r.number(p+8,4);if(o<24||o>=n)throw std::runtime_error("MACHO_BAD_OFFSET");out["dylibs"].push_back({{"name",r.text(p+o,p+n)},{"weak",cmd==0x80000018}});}
 if(cmd==0x8000001c){if(n<12)throw std::runtime_error("MACHO_BAD_RPATH");auto o=r.number(p+8,4);if(o<12||o>=n)throw std::runtime_error("MACHO_BAD_OFFSET");out["rpaths"].push_back(r.text(p+o,p+n));}
 if(cmd==0x24||cmd==0x32){size_t o=cmd==0x32?12:8;if(n<o+8)throw std::runtime_error("MACHO_BAD_VERSION");auto v=r.number(p+o,4);out["min_os"]=std::to_string(v>>16)+"."+std::to_string((v>>8)&255)+"."+std::to_string(v&255);}
 if(cmd==2){if(n<24)throw std::runtime_error("MACHO_BAD_SYMTAB");auto sym=r.number(p+8,4),num=r.number(p+12,4),str=r.number(p+16,4),strsize=r.number(p+20,4);size_t stride=is64?16:12;r.bounds(str,strsize);if(num>r.length/stride)throw std::runtime_error("MACHO_BAD_SYMBOL_COUNT");r.bounds(sym,num*stride);for(size_t j=0;j<num;j++){size_t q=sym+j*stride;auto type=r.number(q+4,1),idx=r.number(q,4);if(!(type&0xe0)&&(type&0xe)==0&&(type&1)&&idx){if(idx>=strsize)throw std::runtime_error("MACHO_BAD_SYMBOL_STRING");out["imports"].push_back(r.text(str+idx,str+strsize));}}}
 p+=n;}
 if(p!=end)throw std::runtime_error("MACHO_COMMAND_BYTES_MISMATCH");return out;
}
Reader slice_reader(const std::vector<uint8_t>& b,size_t base,size_t length){Reader r{b,base,length,false};auto m=r.number(0,4);r.big=m==0xcefaedfe||m==0xcffaedfe;return r;}
}
Json parse_macho(const std::vector<uint8_t>& b){Reader r{b,0,b.size(),true};auto m=r.number(0,4);Json out=Json::array();if(m==0xcafebabe||m==0xcafebabf||m==0xbebafeca||m==0xbfbafeca){r.big=m==0xcafebabe||m==0xcafebabf;bool wide=m==0xcafebabf||m==0xbfbafeca;auto count=r.number(4,4);size_t stride=wide?32:20;if(count>(b.size()-8)/stride)throw std::runtime_error("MACHO_BAD_FAT_COUNT");std::vector<std::pair<size_t,size_t>> ranges;for(size_t i=0;i<count;i++){size_t p=8+i*stride;auto offset=r.number(p+8,wide?8:4),length=r.number(p+(wide?16:12),wide?8:4);r.bounds(offset,length);if(offset<8+count*stride||length<4)throw std::runtime_error("MACHO_BAD_FAT_RANGE");for(auto range:ranges)if(offset<range.first+range.second&&range.first<offset+length)throw std::runtime_error("MACHO_OVERLAPPING_SLICES");ranges.emplace_back(offset,length);auto s=thin(slice_reader(b,offset,length));if(s["arch"]!=arch(r.number(p,4)))throw std::runtime_error("MACHO_FAT_ARCH_MISMATCH");out.push_back(s);}}else out.push_back(thin(slice_reader(b,0,b.size())));return out;}
}
