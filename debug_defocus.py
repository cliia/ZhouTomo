#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
调试脚本：测试 GET/SET defocus 是否生效，并输出详细调试信息。

用法示例：
  python debug_defocus.py --url http://169.254.225.233:9000 --values -5e-8 0 5e-8

注意：
- 脚本会依次尝试多组 defocus 绝对值（单位：米）。
- 每次设置后立即读取 projection/state 并对比落地值。
- 同时尝试两种请求体形态：{"params": {...}} 与 扁平 {...}，便于定位服务端期望的格式。
"""

import asyncio
import json
import sys
import traceback
from typing import List

from agent_client import AgentClient, AgentClientError


def _fmt(v):
    try:
        return f"{float(v):.9e}"
    except Exception:
        return str(v)


async def _get_defocus(client: AgentClient):
    try:
        state = await client._make_request("GET", "/components/projection/state")
        print("[GET state] raw:")
        print(json.dumps(state, ensure_ascii=False, indent=2))
        if isinstance(state, dict):
            df = state.get("defocus")
            print(f"[GET state] defocus(m)= {_fmt(df)}  type={type(df)}")
            return df
        return None
    except Exception as e:
        print(f"[GET state] error: {e}")
        traceback.print_exc()
        return None


async def _set_defocus_body_params(client: AgentClient, value: float):
    body = {"params": {"defocus": float(value)}}
    print(f"[SET defocus params] PATCH /components/projection/params body= {body}")
    try:
        resp = await client._make_request("PATCH", "/components/projection/params", body)
        print("[SET defocus params] resp:")
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return True
    except Exception as e:
        print(f"[SET defocus params] error: {e}")
        traceback.print_exc()
        return False


async def _set_defocus_body_flat(client: AgentClient, value: float):
    body = {"defocus": float(value)}
    print(f"[SET defocus flat] PATCH /components/projection/params body(flat)= {body}")
    try:
        resp = await client._make_request("PATCH", "/components/projection/params", {"params": body})
        print("[SET defocus flat] resp:")
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return True
    except Exception as e:
        print(f"[SET defocus flat] error: {e}")
        traceback.print_exc()
        return False


async def _run_once(url: str, values: List[float], tol: float):
    print(f"[INFO] connecting: {url}")
    async with AgentClient(url) as client:
        # 健康/版本
        try:
            health = await client.get_health()
            print("[health]", json.dumps(health, ensure_ascii=False))
        except Exception as e:
            print("[health] error:", e)
        try:
            version = await client.get_version()
            print("[version]", json.dumps(version, ensure_ascii=False))
        except Exception as e:
            print("[version] error:", e)

        # 初始状态
        print("\n==== INITIAL STATE ====")
        init_df = await _get_defocus(client)

        for idx, target in enumerate(values, 1):
            print("\n===== CASE", idx, "SET ->", _fmt(target), "(m) =====")

            # 方案A：{"params": {"defocus": m}}
            okA = await _set_defocus_body_params(client, target)
            new_dfA = await _get_defocus(client)
            deltaA = None
            try:
                if isinstance(new_dfA, (int, float)):
                    deltaA = float(new_dfA) - float(target)
            except Exception:
                pass
            print(f"[CHECK A] target={_fmt(target)} now={_fmt(new_dfA)} delta={_fmt(deltaA)} ok={okA}")

            # 若A未落地，再试方案B：扁平体
            if not (isinstance(deltaA, float) and abs(deltaA) <= tol):
                okB = await _set_defocus_body_flat(client, target)
                new_dfB = await _get_defocus(client)
                deltaB = None
                try:
                    if isinstance(new_dfB, (int, float)):
                        deltaB = float(new_dfB) - float(target)
                except Exception:
                    pass
                print(f"[CHECK B] target={_fmt(target)} now={_fmt(new_dfB)} delta={_fmt(deltaB)} ok={okB}")

        print("\n==== DONE ====")


def _parse_args(argv: List[str]):
    import argparse
    p = argparse.ArgumentParser(description="Defocus GET/SET 调试脚本")
    p.add_argument("--url", default="http://169.254.225.233:9000", help="服务器URL，如 http://host:9000")
    p.add_argument("--values", nargs="*", type=float, default=[-5e-8, -2e-8, 0.0, 2e-8, 5e-8], help="待设置的defocus值(米)")
    p.add_argument("--tol", type=float, default=5e-12, help="判定落地的容差(米)")
    return p.parse_args(argv)


async def main_async():
    args = _parse_args(sys.argv[1:])
    print("[ARGS]", args)
    try:
        await _run_once(args.url, args.values, args.tol)
    except AgentClientError as e:
        print("[FATAL] AgentClientError:", e)
    except Exception as e:
        print("[FATAL]", e)
        traceback.print_exc()


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()


