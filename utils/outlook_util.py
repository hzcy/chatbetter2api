import base64
import time
import email
import re
import requests
import imaplib
from email.header import decode_header
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Optional
import os

# ----------- 配置 -----------
_OUTLOOK_IMAP_SERVER = "outlook.office365.com"
_CHATBETTER_TITLE_KEY = "ChatBetter"
_MAGIC_LINK_PREFIX = "https://auth.chatbetter.com/oauth/account/activate"
_LOGIN_MAGIC_LINK_PREFIX = "https://auth.chatbetter.com/oauth/account/login/magic-link"
_LUNXUN = 15
_MAIL_TIMEOUT = 3   # 每次查询验证码时的等待时间

# ----------- 解码辅助 -----------
def _safe_decode(payload: bytes, charset: str = "utf-8", errors: str = "ignore") -> str:
    """安全解码字节串，遇到未知编码自动回退到 utf-8 / latin-1。"""
    try:
        return payload.decode(charset or "utf-8", errors)
    except (LookupError, ValueError):  # LookupError: unknown encoding
        try:
            return payload.decode("utf-8", errors)
        except Exception:
            return payload.decode("latin-1", errors)


def _get_access_token(client_id: str, refresh_token: str) -> Optional[str]:
    """使用刷新令牌换取 access token。"""
    data = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    try:
        resp = requests.post("https://login.live.com/oauth20_token.srf", data=data, timeout=15)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        print(f"[Outlook] 获取 access_token 失败: {e}")
        return None


def _generate_auth_string(user: str, token: str) -> str:
    auth_string = f"user={user}\1auth=Bearer {token}\1\1"
    return auth_string


def _extract_magic_link_from_html(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    for a_tag in soup.find_all("a"):
        href = a_tag.get("href")
        if href and (_MAGIC_LINK_PREFIX in href or _LOGIN_MAGIC_LINK_PREFIX in href):
            return href
    return None


def _search_magic_link_in_text(text: str) -> Optional[str]:
    """在纯文本中搜索 ChatBetter 激活链接。"""
    pattern = r"https://auth\.chatbetter\.com/oauth/account/(?:activate|login/magic-link)[\w\-\?=&#%\./]+"
    match = re.search(pattern, text)
    if match:
        link = match.group(0)
        if _MAGIC_LINK_PREFIX in link:
            return link
    return None


def _process_email(msg, expected_recipient: str) -> Tuple[Optional[str], bool]:
    """解析单封邮件，返回 magic_link 和是否收件人匹配。"""
    to_field = msg.get("To", "")
    expected_recipient = expected_recipient.lower()
    recipients = [r.strip().lower() for r in re.split(r",|;", to_field)]
    recipient_match = any(expected_recipient in r for r in recipients)

    # 解码标题
    subject = msg.get("Subject", "")
    decoded_subject = decode_header(subject)[0][0] if subject else ""
    if isinstance(decoded_subject, bytes):
        decoded_subject = decoded_subject.decode("utf-8", errors="replace")

    if not recipient_match:
        return None, False


    try:
        _html_preview, _text_preview = "", ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/html" and not _html_preview:
                    _html_preview = _safe_decode(part.get_payload(decode=True), part.get_content_charset())[:500]
                if ctype == "text/plain" and not _text_preview:
                    _text_preview = _safe_decode(part.get_payload(decode=True), part.get_content_charset())[:500]
        else:
            ctype = msg.get_content_type()
            payload = msg.get_payload(decode=True)
            if payload:
                decoded = _safe_decode(payload, msg.get_content_charset())[:500]
                if ctype == "text/html":
                    _html_preview = decoded
                else:
                    _text_preview = decoded
    except Exception as e:
        pass

    # 如果标题不含关键字，继续后续逻辑以尝试提取链接
    if _CHATBETTER_TITLE_KEY not in decoded_subject:
        pass

    # 提取 HTML
    html = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html = _safe_decode(part.get_payload(decode=True), part.get_content_charset())
                break
    else:
        if msg.get_content_type() == "text/html":
            html = _safe_decode(msg.get_payload(decode=True), msg.get_content_charset())

    magic_link = _extract_magic_link_from_html(html)
    if magic_link:
        return magic_link, recipient_match
    # 如果 HTML 未找到，则尝试在文本中查找
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            try:
                txt = _safe_decode(part.get_payload(decode=True), part.get_content_charset())
            except Exception:
                txt = ""
            magic_link = _search_magic_link_in_text(txt)
            if magic_link:
                return magic_link, recipient_match



    return None, recipient_match


# --------------------------------- 主逻辑 ---------------------------------

class OutlookAccount:
    __slots__ = ("email", "password", "refresh_token", "client_id")

    def __init__(self, email: str, password: str, refresh_token: str, client_id: str):
        self.email = email
        self.password = password  # 目前未使用，但保留以备后续功能
        self.refresh_token = refresh_token
        self.client_id = client_id

    def __repr__(self):
        return f"OutlookAccount({self.email})"


class OutlookMailManager:
    """负责获取邮箱中的magic link。"""

    def __init__(self):
        """初始化邮箱管理器，不再从文件读取账户"""
        pass

    # ------------------- 获取 magic link -------------------

    def get_magic_link(self, account: OutlookAccount) -> Dict[str, str]:
        attempt = 0
        time.sleep(8)
        while attempt < _LUNXUN:
            attempt += 1
            print(f"[Outlook] 第 {attempt}/{_LUNXUN} 次尝试获取 magic link")
            access_token = _get_access_token(account.client_id, account.refresh_token)
            if not access_token:
                time.sleep(_MAIL_TIMEOUT)
                continue
            try:
                mail = imaplib.IMAP4_SSL(_OUTLOOK_IMAP_SERVER)
                mail.authenticate("XOAUTH2", lambda x: _generate_auth_string(account.email, access_token).encode())
                folders = ["INBOX", "Junk", "Junk Email", "Spam", "Bulk Mail", "Clutter"]
                id_list = []
                for fld in folders:
                    try:
                        mail.select(fld)
                        # 先抓 UNSEEN，再抓 ALL
                        status, data = mail.search(None, "UNSEEN")
                        if status != "OK" or not data[0]:
                            status, data = mail.search(None, "ALL")
                        if status == "OK" and data[0]:
                            ids = data[0].split()
                            id_list.extend([(fld, mid) for mid in ids])
                    except Exception:
                        continue
                if not id_list:
                    mail.logout()
                    time.sleep(_MAIL_TIMEOUT)
                    continue
                # 只保留最近 20 封
                id_list = id_list[-20:]
                found_recipient = False
                for fld, msg_id in reversed(id_list):
                    try:
                        mail.select(fld)
                        _, msg_data = mail.fetch(msg_id, "(RFC822)")
                        msg = email.message_from_bytes(msg_data[0][1])
                    except Exception:
                        continue
                    magic_link, recipient_matched = _process_email(msg, account.email)
                    if recipient_matched:
                        found_recipient = True
                    if magic_link and magic_link.startswith(_MAGIC_LINK_PREFIX):
                        mail.logout()
                        return {"type": "True", "link": magic_link}
                mail.logout()
                if found_recipient:
                    # print("[Outlook] 找到收件人匹配邮件，但未提取到链接 (包含其他文件夹)")
                    pass
            except Exception as e:
                print(f"[Outlook] 处理邮箱时异常: {e}")
            time.sleep(_MAIL_TIMEOUT)
        return {"type": "error", "msg": "已到轮询阈值,停止获取"}

    # ------------------- 获取登录 magic link -------------------
    def get_login_link(self, account: OutlookAccount) -> Dict[str, str]:
        """专门用于获取登录邮件中的 magic link。"""
        attempt = 0
        time.sleep(8)
        while attempt < _LUNXUN:
            attempt += 1
            print(f"[Outlook] 第 {attempt}/{_LUNXUN} 次尝试获取 login magic link")
            access_token = _get_access_token(account.client_id, account.refresh_token)
            if not access_token:
                time.sleep(_MAIL_TIMEOUT)
                continue
            try:
                mail = imaplib.IMAP4_SSL(_OUTLOOK_IMAP_SERVER)
                mail.authenticate("XOAUTH2", lambda x: _generate_auth_string(account.email, access_token).encode())
                folders = ["INBOX", "Junk", "Junk Email", "Spam", "Bulk Mail", "Clutter"]
                id_list = []
                for fld in folders:
                    try:
                        mail.select(fld)
                        status, data = mail.search(None, "UNSEEN")
                        if status != "OK" or not data[0]:
                            status, data = mail.search(None, "ALL")
                        if status == "OK" and data[0]:
                            ids = data[0].split()
                            id_list.extend([(fld, mid) for mid in ids])
                    except Exception:
                        continue
                if not id_list:
                    mail.logout()
                    time.sleep(_MAIL_TIMEOUT)
                    continue
                id_list = id_list[-20:]
                found_recipient = False
                for fld, msg_id in reversed(id_list):
                    try:
                        mail.select(fld)
                        _, msg_data = mail.fetch(msg_id, "(RFC822)")
                        msg = email.message_from_bytes(msg_data[0][1])
                    except Exception:
                        continue
                    magic_link, recipient_matched = _process_email(msg, account.email)
                    if recipient_matched:
                        found_recipient = True
                    if magic_link and magic_link.startswith(_LOGIN_MAGIC_LINK_PREFIX):
                        mail.logout()
                        return {"type": "True", "link": magic_link}
                mail.logout()
            except Exception as e:
                print(f"[Outlook] 处理邮箱时异常: {e}")
            time.sleep(_MAIL_TIMEOUT)
        return {"type": "error", "msg": "已到轮询阈值,停止获取登录链接"}

    def print_all_emails(self, account: OutlookAccount, limit: int = 100):
        """打印指定邮箱最近 limit 封邮件的标题。"""
        access_token = _get_access_token(account.client_id, account.refresh_token)
        if not access_token:
            print("[Outlook] 无法获取 access_token，终止")
            return
        try:
            mail = imaplib.IMAP4_SSL(_OUTLOOK_IMAP_SERVER)
            mail.authenticate("XOAUTH2", lambda x: _generate_auth_string(account.email, access_token).encode())
            mail.select("INBOX")
            status, data = mail.search(None, "ALL")
            if status != "OK":
                print("[Outlook] 搜索邮件失败")
                mail.logout()
                return
            id_list = data[0].split()
            if not id_list:
                print("[Outlook] 邮箱为空")
                mail.logout()
                return
            latest_ids = id_list[-limit:] if len(id_list) > limit else id_list
            print(f"[Outlook] 共 {len(id_list)} 封邮件，显示最近 {len(latest_ids)} 封：")
            for idx, msg_id in enumerate(reversed(latest_ids), 1):
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                subject = msg.get("Subject", "<无标题>")
                print(f"{idx}. {subject}")
            mail.logout()
        except Exception as e:
            print(f"[Outlook] 打印邮件时异常: {e}")

# -------------------- CLI Test --------------------
if __name__ == "__main__":
    # 测试方式：直接使用提供的凭据
    test_account_str = "hgrqavgnkwi7@outlook.com----doKA6cwN1JzH----M.C546_BAY.0.U.-CpzVYXDL3YWID1L!CPpFSA3yU1fAT3TArim1T36GmNdk10CcAMC1uQzBAxYjjxL!r6s2tvNpfTd36ITCPZ9IlQUEkrdOZuEahZkw176eHnMKe82ZsSpk26Ibg0CtS0DOcOJTc*8hLvIoUjaxDahQipXysv1ByX27pAyiSkm9!Jx!jLCDihPV3hTDfbG!BuTTAEw0eByJL55TC30O52QschNcQ9j0auN3pUU20z*NoWtQNuWLV4blXPz3gUWNugWNkrU9bAnmTty6tuethjwffWy7NfhiUUC7mSb8odtmJ!zZyNigJY!Fy!HwCQ2GvWaG2UR0Dlp1l*vD!vyfmh3*Xqvz1OnBQSRo5MilADJP79N1SM670MLWZJRq4uKxFkcVj4CyYbThpF5*O75c1rY9IBM$----dbc8e03a-b00c-46bd-ae65-b683e7707cb0"
    
    parts = test_account_str.split("----")
    if len(parts) == 4:
        email_addr, pwd, token, client_id = parts
        print(f"[测试] 使用账号: {email_addr}")
        print(f"[测试] 密码: {pwd[:3]}***")
        print(f"[测试] Client ID: {client_id}")
        
        # 创建测试账户
        test_account = OutlookAccount(email_addr, pwd, token, client_id)
        
        # 创建邮箱管理器
        om = OutlookMailManager()
        
        # 先打印所有邮件标题以查看邮箱内容
        print("\n[测试] 打印邮件标题列表...")
        om.print_all_emails(test_account, limit=20)
        
        # 尝试获取注册链接
        print("\n[测试] 尝试获取ChatBetter注册链接...")
        result = om.get_magic_link(test_account)
        
        if result["type"] == "True":
            print(f"\n[成功] 找到注册链接: {result['link']}")
        else:
            print(f"\n[失败] {result['msg']}")
    else:
        print("[错误] 账户字符串格式不正确，应为：邮箱----密码----token----client_id")

# 示例：如何在其他代码中调用
def example_usage(email_addr: str, password: str, refresh_token: str, client_id: str) -> Optional[str]:
    """
    示例：外部调用获取激活链接
    
    Args:
        email_addr: 邮箱地址
        password: 密码
        refresh_token: 刷新令牌
        client_id: 客户端ID
    
    Returns:
        激活链接或None
    """
    # 创建账户对象
    account = OutlookAccount(email_addr, password, refresh_token, client_id)
    
    # 创建邮箱管理器
    manager = OutlookMailManager()
    
    # 获取激活链接
    result = manager.get_magic_link(account)
    
    if result["type"] == "True":
        return result["link"]
    return None