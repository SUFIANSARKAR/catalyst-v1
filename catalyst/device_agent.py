from __future__ import annotations
import argparse, time
from .config import Settings
from .device import DeviceRegistry, DeviceControlPlane
from .omni import EventLedger, HostDeviceExecutor, DeviceAgent, DeviceAgentConfig

def main():
    ap=argparse.ArgumentParser(description='Catalyst native device actuator')
    ap.add_argument('--device-id',required=True)
    ap.add_argument('--workspace',default='workspace')
    ap.add_argument('--poll',type=float,default=1.0)
    ap.add_argument('--once',action='store_true')
    ap.add_argument('--allow-lock',action='store_true')
    args=ap.parse_args()
    registry=DeviceRegistry('catalyst_data/devices.db')
    control=DeviceControlPlane('catalyst_data/device_commands.db',registry)
    events=EventLedger('catalyst_data/events.db')
    executor=HostDeviceExecutor(args.workspace,args.allow_lock)
    agent=DeviceAgent(control,args.device_id,executor,events,DeviceAgentConfig(args.poll))
    try:
        while True:
            result=agent.run_once()
            if args.once: print(result); break
            time.sleep(max(.1,args.poll))
    finally:
        events.close(); control.close(); registry.close()
if __name__=='__main__': main()
