#!/usr/bin/env python3
"""TempMail Pro - Clean final version with all requested fixes"""
import sys
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6 import QtWidgets, QtCore, QtGui
import qasync
import aiohttp

# Configuration file path
CONFIG_FILE = Path('tempmail_config.json')

# Enhanced dark theme
DARK_THEME = """
QMainWindow {
    background: #0a0b0f;
    color: #ffffff;
    font-family: 'Segoe UI', 'Arial', sans-serif;
}
QWidget {
    background: transparent;
}
QWidget#panel {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1a1e25, stop:1 #161a20);
    border-radius: 16px;
    padding: 16px;
    border: 1px solid rgba(255, 255, 255, 0.1);
}
QWidget#email-item {
    background: #1e2227;
    border-radius: 8px;
    padding: 8px;
}
QLabel {
    color: #ffffff;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1f97b6, stop:1 #178ab8);
    color: #ffffff;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: 600;
    min-width: 60px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #17a2d8, stop:1 #1f97b6);
}
QPushButton:pressed {
    background: #156c87;
}
QPushButton#destructive {
    background: #dc3545;
}
QPushButton#destructive:hover {
    background: #c82333;
}
QListWidget, QTextBrowser, QTextEdit {
    background: #161a20;
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 8px;
    selection-background-color: #1f97b6;
}
QListWidget::item {
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding: 4px;
    background: transparent;
}
QListWidget::item:hover {
    background: rgba(31, 151, 182, 0.1);
}
QListWidget::item:selected {
    background: rgba(31, 151, 182, 0.2);
}
QTabBar::tab {
    background: #161a20;
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 8px 12px;
    border-radius: 4px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #1f97b6;
    border-bottom: 2px solid #17a2d8;
}
QComboBox {
    background: #161a20;
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 4px 8px;
    min-width: 120px;
}
QComboBox::drop-down {
    border: none;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #ffffff;
    margin-right: 5px;
}
QComboBox QAbstractItemView {
    background: #161a20;
    color: #ffffff;
    selection-background-color: #1f97b6;
    border: 1px solid rgba(255, 255, 255, 0.1);
}
QStatusBar {
    background: #161a20;
    color: #ffffff;
}
"""

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DummyCard:
    """Dummy card class to handle compatibility with old config."""
    def update_message_count(self, count):
        pass
    
    def update_email(self, email):
        pass

class EmailListItem(QtWidgets.QWidget):
    """Custom widget for email list items with integrated buttons."""
    copy_signal = QtCore.pyqtSignal(str)
    delete_signal = QtCore.pyqtSignal(str)

    def __init__(self, email: str, count: int, parent=None):
        super().__init__(parent)
        self.setObjectName('email-item')
        self.email = email
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Email text and count
        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setSpacing(2)
        
        self.email_label = QtWidgets.QLabel(email)
        self.email_label.setFont(QtGui.QFont('Segoe UI', 11))
        text_layout.addWidget(self.email_label)
        
        self.count_label = QtWidgets.QLabel(f'{count} messages')
        self.count_label.setFont(QtGui.QFont('Segoe UI', 9))
        self.count_label.setStyleSheet('color: rgba(255, 255, 255, 0.7);')
        text_layout.addWidget(self.count_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()

        # Buttons
        copy_btn = QtWidgets.QPushButton('Copy')
        copy_btn.setFixedWidth(60)
        copy_btn.clicked.connect(lambda: self.copy_signal.emit(email))
        layout.addWidget(copy_btn)

        delete_btn = QtWidgets.QPushButton('Delete')
        delete_btn.setObjectName('destructive')
        delete_btn.setFixedWidth(70)
        delete_btn.clicked.connect(lambda: self.delete_signal.emit(email))
        layout.addWidget(delete_btn)

    def update_count(self, count: int):
        self.count_label.setText(f'{count} messages')
        if count > 0:
            self.count_label.setStyleSheet('color: #17a2d8; font-weight: bold;')
        else:
            self.count_label.setStyleSheet('color: rgba(255, 255, 255, 0.7);')

class TitleBar(QtWidgets.QWidget):
    """Custom title bar with application icon."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('panel')
        self._start_pos = None
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # App icon and title
        icon_label = QtWidgets.QLabel()
        try:
            icon_pixmap = self.style().standardPixmap(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation)
        except:
            icon_pixmap = self.style().standardPixmap(QtWidgets.QStyle.StandardPixmap.SP_FileIcon)
        icon_label.setPixmap(icon_pixmap.scaled(20, 20, QtCore.Qt.AspectRatioMode.KeepAspectRatio))
        layout.addWidget(icon_label)

        title = QtWidgets.QLabel('TempMail Pro')
        title.setFont(QtGui.QFont('Segoe UI', 12, QtGui.QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addStretch()

        # Window controls
        minimize_btn = QtWidgets.QPushButton()
        minimize_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TitleBarMinButton))
        minimize_btn.setFixedSize(24, 24)
        minimize_btn.clicked.connect(parent.showMinimized)
        layout.addWidget(minimize_btn)

        close_btn = QtWidgets.QPushButton()
        close_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TitleBarCloseButton))
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(parent.close)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._start_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._start_pos:
            delta = event.globalPosition().toPoint() - self._start_pos
            self.window().move(self.window().pos() + delta)
            self._start_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

class GuerrillaMailAPI:
    """API handler for Guerrilla Mail service."""
    BASE_URL = 'https://api.guerrillamail.com/ajax.php'
    DOMAINS = ['grr.la', 'sharklasers.com', 'guerrillamail.net', 'guerrillamail.com']

    def __init__(self):
        self.session = aiohttp.ClientSession(headers=self._default_headers())
        self.salt = int(datetime.now().timestamp() * 1000)

    def _default_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': 'TempMailPro/3.0',
            'Accept': 'application/json',
            'Referer': 'https://guerrillamail.com/'
        }

    async def create_address(self, domain: str = None) -> Dict:
        """Create a new email address. If domain is not specified, use first available."""
        if domain is None:
            domain = self.DOMAINS[0]
        
        params = {'f': 'get_email_address', 't': str(self.salt)}
        self.salt += 1
        
        async with self.session.get(self.BASE_URL, params=params) as resp:
            try:
                data = await resp.json()
                return data
            except Exception:
                # Fallback to creating without domain parameter
                params = {'f': 'get_email_address'}
                async with self.session.get(self.BASE_URL, params=params) as fallback_resp:
                    return await fallback_resp.json()

    async def get_messages(self, sid_token: str) -> List[Dict]:
        params = {'f': 'get_email_list', 'sid_token': sid_token, 'offset': '0'}
        async with self.session.get(self.BASE_URL, params=params) as resp:
            data = await resp.json()
            return data.get('list', [])

    async def fetch_message(self, sid_token: str, mail_id: str) -> Dict:
        params = {'f': 'fetch_email', 'sid_token': sid_token, 'email_id': mail_id}
        async with self.session.get(self.BASE_URL, params=params) as resp:
            return await resp.json()

class TempMailApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint)
        self.api = GuerrillaMailAPI()
        self.addresses: Dict[str, Dict] = {}
        self.current_address: Optional[str] = None
        self.refresh_timer = None
        self.unread_counts: Dict[str, int] = {}
        
        # Create dummy card attribute to prevent errors from old config
        self.card = DummyCard()
        
        self._init_ui()
        self._load_config()
        self._setup_auto_refresh()

    def _init_ui(self):
        self.setMinimumSize(700, 500)
        self.setStyleSheet(DARK_THEME)

        # Main container
        container = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        # Stacked pages
        self.stacked = QtWidgets.QStackedWidget()
        main_layout.addWidget(self.stacked, 1)
        self.setCentralWidget(container)

        # Page 0: Email Address & Controls
        addr_page = QtWidgets.QWidget()
        v0 = QtWidgets.QVBoxLayout(addr_page)
        v0.setContentsMargins(16, 16, 16, 16)
        v0.setSpacing(10)

        # Settings panel
        settings_panel = QtWidgets.QWidget()
        settings_panel.setObjectName('panel')
        settings_layout = QtWidgets.QHBoxLayout(settings_panel)
        settings_layout.setContentsMargins(12, 8, 12, 8)
        settings_layout.setSpacing(8)
        
        # Domain selection
        domain_label = QtWidgets.QLabel('Domain:')
        settings_layout.addWidget(domain_label)
        self.combo = QtWidgets.QComboBox()
        self.combo.addItems(self.api.DOMAINS)
        settings_layout.addWidget(self.combo)
        
        settings_layout.addSpacing(10)
        
        # Refresh interval
        refresh_label = QtWidgets.QLabel('Refresh:')
        settings_layout.addWidget(refresh_label)
        self.refresh_combo = QtWidgets.QComboBox()
        self.refresh_combo.addItems(['1 sec', '2 sec', '3 sec', '4 sec', '5 sec', '6 sec', '7 sec', 
                                    '8 sec', '9 sec', '10 sec', '15 sec', '20 sec', '30 sec', 
                                    '40 sec', '50 sec', '60 sec'])
        self.refresh_combo.setCurrentText('5 sec')
        self.refresh_combo.currentTextChanged.connect(self._update_refresh_interval)
        settings_layout.addWidget(self.refresh_combo)
        
        settings_layout.addStretch()
        
        create_btn = QtWidgets.QPushButton('Create New Email')
        create_btn.clicked.connect(lambda: asyncio.create_task(self._create_address()))
        settings_layout.addWidget(create_btn)
        
        v0.addWidget(settings_panel)

        # Address list with custom widgets
        self.addr_list = QtWidgets.QListWidget()
        self.addr_list.itemClicked.connect(self._on_addr_selected)
        v0.addWidget(self.addr_list)

        self.stacked.addWidget(addr_page)

        # Page 1: Inbox
        in_page = QtWidgets.QWidget()
        vi = QtWidgets.QVBoxLayout(in_page)
        vi.setContentsMargins(16, 16, 16, 16)
        vi.setSpacing(10)

        # Header with navigation
        header_layout = QtWidgets.QHBoxLayout()
        back0 = QtWidgets.QPushButton('← Back to Addresses')
        back0.clicked.connect(self._show_home_page)
        header_layout.addWidget(back0)
        
        refresh_inbox_btn = QtWidgets.QPushButton('↻ Check Messages')
        refresh_inbox_btn.clicked.connect(lambda: asyncio.create_task(self._refresh_messages()))
        header_layout.addWidget(refresh_inbox_btn)
        header_layout.addStretch()
        
        vi.addLayout(header_layout)

        self.msg_list = QtWidgets.QListWidget()
        self.msg_list.itemClicked.connect(self._on_msg_selected)
        vi.addWidget(self.msg_list)

        self.stacked.addWidget(in_page)

        # Page 2: Message View
        msg_page = QtWidgets.QWidget()
        vm = QtWidgets.QVBoxLayout(msg_page)
        vm.setContentsMargins(16, 16, 16, 16)
        vm.setSpacing(10)

        # Tabs with back button at the same level (horizontal layout)
        tabs_layout = QtWidgets.QHBoxLayout()
        tabs_layout.setSpacing(0)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QtWidgets.QTabWidget()
        self.html_view = QtWidgets.QTextBrowser()
        self.html_view.setOpenExternalLinks(True)
        self.raw_view = QtWidgets.QTextEdit()
        self.raw_view.setReadOnly(True)
        self.tabs.addTab(self.html_view, 'HTML Preview')
        self.tabs.addTab(self.raw_view, 'Raw Data')
        
        # Add tabs to layout with stretch
        tabs_layout.addWidget(self.tabs, 1)
        
        # Create back button with same height as tab bar
        back1 = QtWidgets.QPushButton('← Back to Inbox')
        back1.clicked.connect(self._show_inbox_page)
        
        # Set the button height to match tab bar
        QtCore.QTimer.singleShot(0, lambda: back1.setFixedHeight(self.tabs.tabBar().height()))
        
        tabs_layout.addWidget(back1)
        
        vm.addLayout(tabs_layout)

        self.stacked.addWidget(msg_page)

        # Hidden error frame
        self.error_frame = QtWidgets.QFrame()
        self.error_frame.setObjectName('panel')
        self.error_frame.setFixedHeight(30)
        self.error_frame.hide()
        
        error_layout = QtWidgets.QHBoxLayout(self.error_frame)
        error_layout.setContentsMargins(16, 8, 16, 8)
        
        self.error_label = QtWidgets.QLabel()
        self.error_label.setStyleSheet('color: #dc3545; font-weight: bold;')
        error_layout.addWidget(self.error_label)
        
        close_error_btn = QtWidgets.QPushButton('✕')
        close_error_btn.setFixedSize(20, 20)
        close_error_btn.clicked.connect(self.error_frame.hide)
        error_layout.addWidget(close_error_btn)
        
        main_layout.addWidget(self.error_frame)

        # Status bar
        self.statusBar().setStyleSheet('padding: 5px;')

    def _show_home_page(self):
        """Navigate to home/addresses page."""
        self.stacked.setCurrentIndex(0)
        
    def _show_inbox_page(self):
        """Navigate to inbox page."""
        self.stacked.setCurrentIndex(1)
        
    def _show_message_page(self):
        """Navigate to message view page."""
        self.stacked.setCurrentIndex(2)

    def show_error(self, message: str):
        """Show error message in the error frame."""
        self.error_label.setText(message)
        self.error_frame.show()

    def hide_error(self):
        """Hide error frame."""
        self.error_frame.hide()

    def _setup_auto_refresh(self):
        """Setup automatic refresh timer for mail checking."""
        self.refresh_timer = QtCore.QTimer()
        self.refresh_timer.timeout.connect(self._auto_refresh_messages)
        self.refresh_timer.start(5000)  # Default 5 seconds

    def _update_refresh_interval(self):
        """Update the refresh interval when user changes it."""
        if self.refresh_timer:
            value = int(self.refresh_combo.currentText().split()[0])
            self.refresh_timer.stop()
            self.refresh_timer.start(value * 1000)

    def _auto_refresh_messages(self):
        """Automatically check for new messages for all addresses."""
        asyncio.create_task(self._async_refresh_all())

    async def _async_refresh_all(self):
        """Asynchronously check all addresses for new messages."""
        # Skip refresh if this is an old instance that's still running
        if not hasattr(self, 'addr_list') or not hasattr(self, 'msg_list'):
            return
            
        for addr, data in self.addresses.items():
            try:
                sid = data['sid_token']
                msgs = await self.api.get_messages(sid)
                old_count = len(data.get('messages', []))
                new_count = len(msgs)
                
                # Update message count
                self.unread_counts[addr] = new_count
                data['messages'] = msgs
                
                # Update UI if this is the current address
                if addr == self.current_address:
                    if hasattr(self, 'msg_list'):
                        self._update_message_list(msgs)
                    # Handle compatibility with old version
                    if hasattr(self, 'card') and hasattr(self.card, 'update_message_count'):
                        self.card.update_message_count(new_count)
                
                # Show notification if new messages
                if new_count > old_count:
                    self.statusBar().showMessage(f'📬 New message for {addr}', 5000)
                    
            except Exception as e:
                logging.error(f'Error refreshing {addr}: {e}')
        
        self._update_address_list()

    async def _create_address(self, domain: str = None):
        """Create a new email address."""
        try:
            # Close the existing session and create a new one
            await self.api.session.close()
            self.api = GuerrillaMailAPI()
            
            # If domain not specified, use selected domain
            if domain is None:
                domain = self.combo.currentText()
            
            resp = await self.api.create_address(domain)
            addr = resp.get('email_addr')
            sid = resp.get('sid_token')
            
            if not addr or not sid:
                raise ValueError('Invalid server response')
            
            self.addresses[addr] = {'sid_token': sid, 'messages': []}
            self.unread_counts[addr] = 0
            self.current_address = addr
            self._update_address_list()
            self.statusBar().showMessage(f'✓ Created: {addr}', 3000)
            self.hide_error()
            
        except Exception as e:
            error_msg = f'Error creating email: {str(e)}'
            logging.error(error_msg)
            self.show_error(error_msg)

    async def _refresh_messages(self):
        """Refresh messages for current address."""
        if not self.current_address:
            return
        try:
            sid = self.addresses[self.current_address]['sid_token']
            msgs = await self.api.get_messages(sid)
            self.addresses[self.current_address]['messages'] = msgs
            self.unread_counts[self.current_address] = len(msgs)
            self._update_message_list(msgs)
            self.statusBar().showMessage('📬 Inbox refreshed', 2000)
        except Exception as e:
            error_msg = f'Error refreshing messages: {str(e)}'
            logging.error(error_msg)
            self.show_error(error_msg)

    async def _show_message(self, mail_id: str):
        """Display a specific message."""
        try:
            sid = self.addresses[self.current_address]['sid_token']
            msg = await self.api.fetch_message(sid, mail_id)
            html = msg.get('mail_body', '')
            
            # Enhanced metadata display without border
            meta = f"""
            <div style="margin-bottom: 16px;">
                <h3 style="margin: 10px 0; color: white;">📧 {msg.get('subject', 'No Subject')}</h3>
                <p style="margin: 8px 0; color: rgba(255,255,255,0.9);">
                    <strong>From:</strong> {msg.get('mail_from', 'Unknown')}<br>
                    <strong>Date:</strong> {self._fmt(ts=msg.get('mail_date'))}<br>
                    <strong>Size:</strong> {self._format_size(msg.get('mail_size', 0))}
                </p>
                <hr style="border-color: #333;">
            </div>
            """
            self.html_view.setHtml(meta + html)
            self.raw_view.setPlainText(json.dumps(msg, indent=2))
        except Exception as e:
            error_msg = f'Error loading message: {str(e)}'
            logging.error(error_msg)
            self.html_view.setHtml(f'<p style="color: #dc3545;">{error_msg}</p>')
            self.raw_view.clear()
            self.show_error(error_msg)

    def _on_addr_selected(self, item: QtWidgets.QListWidgetItem):
        """Handle address selection."""
        # Get the actual email address from the custom widget
        widget = self.addr_list.itemWidget(item)
        if isinstance(widget, EmailListItem):
            addr = widget.email
            self.current_address = addr
            if addr in self.unread_counts:
                msg_count = self.unread_counts[addr]
            else:
                msg_count = 0
            self.stacked.setCurrentIndex(1)
            asyncio.create_task(self._refresh_messages())

    def _on_msg_selected(self, item: QtWidgets.QListWidgetItem):
        """Handle message selection."""
        mail_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        self._show_message_page()
        asyncio.create_task(self._show_message(mail_id))

    def _delete_address(self, addr: str):
        """Delete a specific address."""
        if addr and addr in self.addresses:
            del self.addresses[addr]
            if addr in self.unread_counts:
                del self.unread_counts[addr]
            
            if addr == self.current_address:
                self.current_address = None
                self.msg_list.clear()
            
            self._update_address_list()

    def _copy_email(self, email: str):
        """Copy email to clipboard."""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(email)
        self.statusBar().showMessage(f'✓ Copied: {email}', 3000)

    def _update_address_list(self):
        """Update the address list with custom widgets."""
        self.addr_list.clear()
        for addr in self.addresses:
            count = self.unread_counts.get(addr, 0)
            
            # Create custom list item
            item = QtWidgets.QListWidgetItem()
            item.setSizeHint(QtCore.QSize(0, 50))  # Set item height
            
            # Create custom widget
            widget = EmailListItem(addr, count)
            widget.copy_signal.connect(self._copy_email)
            widget.delete_signal.connect(self._delete_address)
            
            self.addr_list.addItem(item)
            self.addr_list.setItemWidget(item, widget)

    def _update_message_list(self, messages: List[Dict]):
        """Update the message list."""
        # Handle case where object is from an older version
        if not hasattr(self, 'msg_list'):
            return
            
        self.msg_list.clear()
        for msg in reversed(messages):
            subj = msg.get('subject', 'No Subject')
            sender = msg.get('mail_from', 'Unknown')
            date = self._fmt(ts=msg.get('mail_date'))
            
            # Create enhanced message display
            display_text = f'{subj}\nFrom: {sender} • {date}'
            item = QtWidgets.QListWidgetItem(display_text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, msg.get('mail_id'))
            
            # Highlight unread messages
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            
            self.msg_list.addItem(item)

    def _fmt(self, ts):
        """Format timestamp to readable date."""
        try:
            # Handle both string and integer timestamps
            if isinstance(ts, str):
                ts = int(ts)
            elif ts is None:
                return ''
            dt = datetime.fromtimestamp(ts)
            return dt.strftime('%Y-%m-%d %H:%M')
        except (ValueError, TypeError):
            # Return original value if conversion fails
            return str(ts) if ts is not None else ''

    def _format_size(self, size):
        """Format email size in human-readable format."""
        try:
            # Convert to integer if it's a string
            if isinstance(size, str):
                size = int(size)
            elif size is None:
                return '0 B'
                
            if size < 1024:
                return f'{size} B'
            elif size < 1024 * 1024:
                return f'{size/1024:.1f} KB'
            else:
                return f'{size/(1024*1024):.1f} MB'
        except (ValueError, TypeError):
            return '0 B'

    def _load_config(self):
        """Load saved configuration."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    data = json.load(f)
                    self.addresses = data.get('addresses', {})
                    self.unread_counts = data.get('unread_counts', {})
                    if self.addresses:
                        self.current_address = next(iter(self.addresses))
                        # Only update address list if the object is fully initialized
                        if hasattr(self, 'addr_list'):
                            self._update_address_list()
            except Exception as e:
                logging.error(e)

    def closeEvent(self, event):
        """Save configuration on close."""
        try:
            config_data = {
                'addresses': self.addresses,
                'unread_counts': self.unread_counts
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            logging.error(e)
        asyncio.run(self.api.session.close())
        event.accept()

async def main():
    """Main entry point."""
    try:
        app = QtWidgets.QApplication(sys.argv)
        window = TempMailApp()
        window.show()
        await asyncio.Future()
    except Exception as e:
        logging.error(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    try:
        qasync.run(main())
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)