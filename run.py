import asyncio
import yourgod
import sys

async def main():
    print("Module 'yourgod' ကို အောင်မြင်စွာ load လုပ်ပြီးပါပြီ။")
    print("Menu ကို စတင်နေပါပြီ...")
    
    try:
        # start_menu ကို async နည်းလမ်းနဲ့ run ခြင်း
        if hasattr(yourgod, 'start_menu'):
            result = yourgod.start_menu()
            # အကယ်၍ result က coroutine ဖြစ်နေရင် await လုပ်ပါ
            if asyncio.iscoroutine(result):
                await result
            else:
                # တခါတလေ start_menu က sync function ဖြစ်ပြီး အတွင်းမှာ async ကို ခေါ်တာမျိုးလည်း ရှိနိုင်ပါတယ်
                pass 
        else:
            print("Error: 'start_menu' function ကို module ထဲမှာ ရှာမတွေ့ပါ။")
            print("ရရှိနိုင်သော functions များ -", dir(yourgod))
            
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    try:
        # Async loop ကို စတင်ခြင်း
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nအသုံးပြုသူမှ ပိတ်လိုက်ပါသည်။")
    except Exception as e:
        print(f"Main error: {e}")
