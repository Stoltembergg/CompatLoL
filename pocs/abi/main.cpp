// SPDX-License-Identifier: GPL-3.0-only
// Open synthetic Mach-O fixture; passing on macOS does not validate Darling.
#include <thread>
#include <stdexcept>
#include <iostream>
#include <atomic>
thread_local int tls=7;
int main(){std::atomic<int>result{0};std::thread worker([&]{tls=11;result=tls;});worker.join();if(tls!=7||result!=11)return 1;try{throw std::runtime_error("fixture");}catch(const std::runtime_error&){std::cout<<"tls/thread/unwind fixture passed\n";}return 0;}
