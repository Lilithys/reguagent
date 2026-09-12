#!/usr/bin/env python3
"""Run in the terminal that already has the exported key; does not display it."""
import argparse
from llm_config import capture_deepseek_environment


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-env',action='store_true',required=True)
    parser.add_argument('--model',default='deepseek-v4-flash')
    args=parser.parse_args()
    try:path=capture_deepseek_environment(model=args.model)
    except FileExistsError:parser.exit(2,'Local .env.local already exists; preserved without overwriting.\n')
    except ValueError as exc:parser.exit(2,str(exc)+'\n')
    print(f'Configuration saved to {path}; key was not printed. File permissions: owner read/write.')


if __name__=='__main__':main()
