import asyncio
import sys
import os

async def execute_binary():
    # Clear screen for premium UI layout
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("\033[1;36m┌──────────────────────────────────────────────┐\033[0m")
    print("\033[1;36m│             LAUNCHING CORE ENGINE            │\033[0m")
    print("\033[1;36m└──────────────────────────────────────────────┘\033[0m")
    print("\033[0;90m[*] Initializing handshake with binary module...\033[0m")

    try:
        # cc.so ဖိုင်ကို လှမ်းပြီး Import ဆွဲသွင်းခြင်း
        import cc
    except ModuleNotFoundError:
        print("\n\033[1;31m[!] Critical Error: 'cc.so' library file not found.\033[0m")
        print("\033[0;37m[#] Ensure 'cc.so' is placed in the exact same folder.\033[0m\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n\033[1;31m[!] Failed to load binary module: {e}\033[0m\n")
        sys.exit(1)

    # cc.so ထဲက အဓိက main() function ကို လှမ်းခေါ်ယူခြင်း
    if hasattr(cc, 'main'):
        try:
            result = cc.main()
            # အကယ်၍ main က async function ဖြစ်နေခဲ့ရင် await လုပ်ပေးမယ်
            if asyncio.iscoroutine(result) or asyncio.iscoroutinefunction(cc.main):
                await result
        except Exception as e:
            print(f"\n\033[1;31m[!] Runtime Error inside binary execution: {e}\033[0m\n")
    else:
        print("\n\033[1;31m[!] Error: 'main' entry point function not found inside cc.so.\033[0m\n")

if __name__ == "__main__":
    try:
        asyncio.run(execute_binary())
    except KeyboardInterrupt:
        print("\n\033[1;33m[!] Process aborted by user.\033[0m\n")
    except Exception as e:
        print(f"\n\033[1;31m[!] Fatal Main Exception: {e}\033[0m\n")
        
