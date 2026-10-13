// SPDX-License-Identifier: GPL-3.0-only
#include "macho.hpp"
#include "host.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sys/utsname.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#ifdef __APPLE__
#include <CommonCrypto/CommonDigest.h>
#else
#include <openssl/sha.h>
#endif
#include <sstream>
#include <iomanip>
using compatlol::Json;
namespace fs=std::filesystem;
std::string hash(const std::vector<uint8_t>& b){unsigned char d[32];
#ifdef __APPLE__
CC_SHA256(b.data(),static_cast<CC_LONG>(b.size()),d);
#else
SHA256(b.data(),b.size(),d);
#endif
std::ostringstream s;for(auto c:d)s<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(c);return s.str();}
int main(int argc,char** argv){std::string run_id="unavailable";try{run_id=compatlol::new_run_id();if(argc<2)throw std::runtime_error("USAGE_REQUIRED");std::string cmd=argv[1];
if(cmd=="doctor"){if(argc!=3||std::string(argv[2])!="--json")throw std::runtime_error("DOCTOR_REQUIRES_JSON");std::cout<<compatlol::host_report().dump(2)<<"\n";return 0;}
if(cmd=="run")throw std::runtime_error("EXECUTION_BLOCKED: runtime/GPU validation and reviewed authorization not implemented; flags cannot unlock execution");
if(cmd!="inspect")throw std::runtime_error("UNKNOWN_COMMAND");fs::path bundle,out;for(int i=2;i<argc;i++){std::string a=argv[i];if((a=="--bundle"||a=="--out")&&i+1<argc){if(a=="--bundle")bundle=argv[++i];else out=argv[++i];}else throw std::runtime_error("INVALID_ARGUMENT");}if(bundle.empty()||out.empty())throw std::runtime_error("BUNDLE_AND_OUT_REQUIRED");if(fs::is_symlink(bundle)||!fs::is_directory(bundle))throw std::runtime_error("BUNDLE_MUST_BE_REAL_DIRECTORY");auto root=fs::canonical(bundle);auto output=fs::weakly_canonical(out);auto rel=output.lexically_relative(root);if(!rel.empty()&&*rel.begin()!="..")throw std::runtime_error("OUTPUT_MUST_BE_OUTSIDE_BUNDLE");Json j={{"schema_version",1},{"bundle_version",nullptr},{"binaries",Json::array()},{"requirements",Json::array()}};
for(auto& e:fs::recursive_directory_iterator(root)){if(e.is_symlink()||!e.is_regular_file())continue;std::ifstream f(e.path(),std::ios::binary);unsigned char magic[4]{};f.read(reinterpret_cast<char*>(magic),4);if(f.gcount()!=4)continue;uint32_t m=(uint32_t(magic[0])<<24)|(uint32_t(magic[1])<<16)|(uint32_t(magic[2])<<8)|magic[3];if(m!=0xfeedface&&m!=0xfeedfacf&&m!=0xcefaedfe&&m!=0xcffaedfe&&m!=0xcafebabe&&m!=0xcafebabf&&m!=0xbebafeca&&m!=0xbfbafeca)continue;auto size=e.file_size();if(size>256*1024*1024)throw std::runtime_error("INSPECTION_SIZE_LIMIT");f.seekg(0);std::vector<uint8_t>b(size);f.read(reinterpret_cast<char*>(b.data()),size);if(!f)throw std::runtime_error("READ_FAILED");auto slices=compatlol::parse_macho(b);j["binaries"].push_back({{"relative_path",e.path().lexically_relative(root).generic_string()},{"sha256",hash(b)},{"slices",slices}});}
// Serialize before opening; refuse existing files (including hard-link aliases).
std::string serialized=j.dump(2)+"\n";
int fd=open(out.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
if(fd<0)throw std::runtime_error("OUTPUT_MUST_BE_NEW_FILE");
size_t offset=0;while(offset<serialized.size()){ssize_t n=write(fd,serialized.data()+offset,serialized.size()-offset);if(n<0&&errno==EINTR)continue;if(n<=0){close(fd);throw std::runtime_error("OUTPUT_WRITE_FAILED");}offset+=size_t(n);}if(close(fd))throw std::runtime_error("OUTPUT_CLOSE_FAILED");return 0;
}catch(const std::exception& e){// Do not leak paths from filesystem exceptions into logs.
const auto* filesystem_error=dynamic_cast<const fs::filesystem_error*>(&e);
std::string message=filesystem_error?"FILESYSTEM_OPERATION_FAILED":e.what();
std::cerr<<compatlol::log_record(run_id,"error","OPERATION_REFUSED",message).dump(-1,' ',false,Json::error_handler_t::replace)<<"\n";return 2;}}
