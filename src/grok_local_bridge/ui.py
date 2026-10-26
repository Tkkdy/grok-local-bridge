"""Local-only credential input/display. Never prints or auto-copies a secret."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from ._vendor.ar_dpapi import load_credential
from .io_utils import read_json
from .secret_store import SecretStore

def owner_window(home):
    from .processes import manager_alive
    home=Path(home).resolve()
    if not manager_alive(home): raise ValueError("manager_not_running")
    status=read_json(home/"status.json")
    state=Path(status["state_dir"]).resolve()
    if not state.is_relative_to(home/"oauth"): raise ValueError("invalid state location")
    owner=load_credential(state/"owner.dpapi")
    root=tk.Tk();root.title("Grok Local Bridge - 连接授权");root.geometry("720x280")
    frame=ttk.Frame(root,padding=18);frame.pack(fill="both",expand=True)
    ttk.Label(frame,text="在 GrokBot 添加远程 MCP，并选择 OAuth。").pack(anchor="w")
    url=ttk.Entry(frame);url.insert(0,status["mcp_url"]);url.configure(state="readonly");url.pack(fill="x",pady=10)
    ttk.Label(frame,text="本次授权码只用于此连接的 OAuth 页面，请勿发送到聊天。").pack(anchor="w")
    entry=ttk.Entry(frame,show="*");entry.insert(0,owner);entry.configure(state="readonly");entry.pack(fill="x",pady=10)
    def copy(): root.clipboard_clear();root.clipboard_append(owner)
    ttk.Button(frame,text="复制授权码",command=copy).pack(anchor="w")
    ttk.Button(frame,text="完成，关闭窗口",command=root.destroy).pack(anchor="e")
    root.mainloop()

def secret_window(home,name):
    store=SecretStore(Path(home)/"secrets");store.slot_path(name)
    root=tk.Tk();root.title("Grok Local Bridge - 安全凭据输入");root.geometry("600x210")
    frame=ttk.Frame(root,padding=18);frame.pack(fill="both",expand=True)
    ttk.Label(frame,text="凭据槽位："+name+"；加密保存到当前 Windows 用户。").pack(anchor="w")
    entry=ttk.Entry(frame,show="*");entry.pack(fill="x",pady=12);entry.focus_set()
    notice=tk.StringVar(value="不要把凭据填入命令行、配置或聊天。");ttk.Label(frame,textvariable=notice).pack(anchor="w")
    def save():
        try: store.save(name,entry.get());entry.delete(0,"end");notice.set("已加密保存，可关闭窗口。")
        except Exception: notice.set("保存失败，请检查输入与当前用户权限。")
    ttk.Button(frame,text="加密保存",command=save).pack(anchor="w",pady=12)
    root.mainloop()
