#!/usr/bin/env python3
# Developed by: https://github.com/zebbern
"""TempMail Pro - Compact version with minimal UI and multiple services"""
import sys
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from time import time  # Added for timers
import re  # For URL detection
import sys
from PyQt6.QtCore import Qt, QPoint
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import QApplication
import qasync
import aiohttp

# Import all our API classes
from temp_mail_apis import SERVICE_REGISTRY, GuerrillaMailAPI

# Configuration file path
CONFIG_FILE = Path('tempmail_config.json')
MESSAGES_FILE = Path('tempmail_messages.json')  # For persisting messages

# Add this import
import warnings

# Add these lines to suppress the warning
warnings.filterwarnings("ignore", message="Unclosed client session")
warnings.filterwarnings("ignore", message="Unclosed connector")

# Minimal dark theme
DARK_THEME = """
QMainWindow {
    background: #0a0b0f;
    color: #ffffff;
    font-family: 'Segoe UI', 'Arial', sans-serif;
}
QWidget {
    background: transparent;
}
QWidget#main-container {
    background: #1a1e25;
    border-radius: 8px;
    padding: 8px;
}
QWidget#email-item {
    background: #1e2227;
    border-radius: 4px;
    padding: 6px;
}
QLabel {
    color: #ffffff;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1f97b6, stop:1 #178ab8);
    color: #ffffff;
    border: none;
    padding: 6px 12px;
    border-radius: 4px;
    font-weight: 600;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #17a2d8, stop:1 #1f97b6);
}
QPushButton:pressed {
    background: #156c87;
}
QPushButton#destructive {
        background: #7c2328;
        height: 22px;
        border: 1px solid #dc3545;
        border-radius: 2px;
        color: #ffffff;
        padding: 0px;
        font-size: 13px;
    }
    QPushButton#destructive:hover {
        background: #dc3545;
    }
QListWidget, QTextBrowser, QTextEdit {
    background: #161a20;
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #1f97b6;
}
QListWidget::item {
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding: 3px;
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
    padding: 6px 10px;
    border-radius: 4px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #1f97b6;
    border-bottom: 2px solid #17a2d8;
}
QStatusBar {
    background: #161a20;
    color: #ffffff;
}
QComboBox {
    background: #161a20;
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 120px;
}
QComboBox::drop-down::after {
    font-size: 14px;
    color: white;
    margin-right: 6px;
}
QMenu {
    background-color: #1a1e25;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 10px;
    border-radius: 3px;
}
QMenu::item:selected {
    background: rgba(31, 151, 182, 0.2);
}
QMenu::separator {
    height: 1px;
    background: rgba(255, 255, 255, 0.1);
    margin: 4px 0px;
}
QMenu::indicator {
    width: 16px;
    height: 16px;
    left: 6px;
}
QFrame#settings-separator {
    background-color: rgba(255, 255, 255, 0.1);
    max-height: 1px;
    min-height: 1px;
}
QLabel#settings-header {
    font-size: 14px;
    font-weight: bold;
    color: #17a2d8;
    padding: 5px 0;
}
"""

# Set logging level to warn to remove INFO outputs
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

class DummyCard:
    """Dummy card class to handle compatibility with old config."""
    def update_message_count(self, count):
        pass
    
    def update_email(self, email):
        pass

class EmailListItem(QtWidgets.QWidget):
    """Compact custom widget for email list items."""
    copy_signal = QtCore.pyqtSignal(str)
    delete_signal = QtCore.pyqtSignal(str)

    def __init__(self, email: str, count: int, service: str, created_at=None, expiry_seconds=3600, parent=None):
        super().__init__(parent)
        self.setObjectName('email-item')
        self.email = email
        self.created_at = created_at
        self.expiry_seconds = expiry_seconds
        self.timer = None
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        # Email text and count with service badge
        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setSpacing(1)
        
        # Email and service in one row
        email_layout = QtWidgets.QHBoxLayout()
        email_layout.setSpacing(6)
        email_layout.setContentsMargins(0, 0, 0, 0)
        
        self.email_label = QtWidgets.QLabel(email)
        self.email_label.setFont(QtGui.QFont('Segoe UI', 10))
        email_layout.addWidget(self.email_label)
        
        # Service badge
        service_label = QtWidgets.QLabel(service)
        service_label.setFont(QtGui.QFont('Segoe UI', 8))
        service_label.setStyleSheet("""
            background: #1f97b6;
            color: #ffffff;
            padding: 2px 6px;
            border-radius: 3px;
        """)
        email_layout.addWidget(service_label)
        email_layout.addStretch()
        
        text_layout.addLayout(email_layout)
        
        # Info row with message count and timer - now with fixed widths
        info_layout = QtWidgets.QHBoxLayout()
        info_layout.setSpacing(10)
        
        # Count label with box and proper pluralization
        count_text = f"{count} mail" if count == 1 else f"{count} mails"
        self.count_label = QtWidgets.QLabel(count_text)
        self.count_label.setFont(QtGui.QFont('Segoe UI', 8))
        self.count_label.setStyleSheet("""
    color: #FFF;
    background-color: rgba(50, 50, 50, 0.5);
    border: 1px solid rgba(200, 200, 200, 0.7);   /* <-- add a light border */
    border-radius: 2px;                            /* <-- bigger rounding */
    padding: 2px 2px;                              /* <-- more inner space */
""")

        self.count_label.setFixedWidth(70)  # Fixed width for alignment
        self.count_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)  # Center text
        info_layout.addWidget(self.count_label)
        
        # Add timer label with fixed width
        self.timer_label = QtWidgets.QLabel("00:00:00")
        self.timer_label.setFont(QtGui.QFont('Segoe UI', 8))
        self.timer_label.setStyleSheet('color: #17a2d8;')
        self.timer_label.setFixedWidth(80)  # Fixed width for alignment
        self.timer_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)  # Center text
        info_layout.addWidget(self.timer_label)
        info_layout.addStretch()
        
        text_layout.addLayout(info_layout)
        
        layout.addLayout(text_layout)
        layout.addStretch()

        # Compact buttons
        copy_btn = QtWidgets.QPushButton('Copy')
        copy_btn.setFixedWidth(50)
        copy_btn.setFixedHeight(24)
        copy_btn.clicked.connect(lambda: self.copy_signal.emit(email))
        layout.addWidget(copy_btn)
        copy_btn.setStyleSheet("""
    QPushButton {
        background: #294560;
        border: 1px solid #1f97b6;
        border-radius: 1px;
        color: #ffffff;
        padding: 0px;
        font-size: 12px;
    }
    QPushButton:hover {
        background: #1f97b6;
    }
""")
        

        delete_btn = QtWidgets.QPushButton('🗑️')
        delete_btn.setObjectName('destructive')
        delete_btn.setFixedWidth(25)
        delete_btn.clicked.connect(lambda: self.delete_signal.emit(email))
        layout.addWidget(delete_btn)
        
        # Start the timer update if we have creation time
        if created_at:
            self.start_timer()

    def update_count(self, count: int):
        """Update count label with proper pluralization"""
        count_text = f"{count} mail" if count == 1 else f"{count} mails"
        self.count_label.setText(count_text)
        if count > 0:
            self.count_label.setStyleSheet("""
                color: #17a2d8;
                font-weight: bold;
                background-color: rgba(50, 50, 50, 0.5);
                border-radius: 1px;
                padding: 2px 3px;
            """)
        else:
            self.count_label.setStyleSheet("""
                color: rgba(255, 255, 255, 0.7);
                background-color: rgba(50, 50, 50, 0.5);
                border-radius: 2px;
                padding: 2px 6px;
            """)
    
    def start_timer(self):
        """Start the countdown timer"""
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(1000)  # Update every second
        self.update_timer()  # Initial update
    
    def update_timer(self):
        """Update the timer display"""
        if not self.created_at:
            return
            
        elapsed = time() - self.created_at
        remaining = max(0, self.expiry_seconds - elapsed)
        
        # Format as HH:MM:SS
        days    = int(remaining // 86400)
        hours   = int((remaining % 86400) // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)
        timer_text = f"{days} days {hours:02d}:{minutes:02d}:{seconds:02d}"
        
        self.timer_label.setText(timer_text)
        
        # Change color based on remaining time
        if remaining <= 300:  # Less than 5 minutes
            self.timer_label.setStyleSheet('color: #dc3545; font-weight: bold;')
        elif remaining <= 900:  # Less than 15 minutes
            self.timer_label.setStyleSheet('color: #ffc107; font-weight: bold;')
        else:
            self.timer_label.setStyleSheet('color: #17a2d8;')

class CompactToolbar(QtWidgets.QWidget):
    """Compact toolbar that replaces settings panel and title bar."""
    create_signal = QtCore.pyqtSignal()
    settings_signal = QtCore.pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)  # Compact height
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        
        # Service selector - use class SERVICE_NAME constant without instantiation
        self.service_combo = QtWidgets.QComboBox()
        for key, api_class in SERVICE_REGISTRY.items():
            self.service_combo.addItem(api_class.SERVICE_NAME, key)
        layout.addWidget(self.service_combo)
        
        # Create button
        create_btn = QtWidgets.QPushButton('✚')
        create_btn.setFixedWidth(40)
        create_btn.setFixedHeight(22)
        create_btn.clicked.connect(self.create_signal.emit)
        layout.addWidget(create_btn)
        
        layout.addStretch()
        
        # Settings button (for dropdown options)
        settings_btn = QtWidgets.QPushButton('⚙︎')
        settings_btn.setFixedWidth(42)
        settings_btn.clicked.connect(self.settings_signal.emit)
        layout.addWidget(settings_btn)
        
        # Close button
        close_btn = QtWidgets.QPushButton('⛌')
        close_btn.setFixedWidth(42)
        close_btn.clicked.connect(parent.close)
        layout.addWidget(close_btn)

    def get_selected_service(self) -> str:
        """Get the currently selected service key"""
        return self.service_combo.currentData()

class SettingsDialog(QtWidgets.QDialog):
    """Enhanced settings dialog for better visualization"""
    def __init__(self, parent=None, current_domain=None, domains=None, 
                refresh_interval=3, on_domain_change=None, on_interval_change=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedWidth(300)
        self.setFixedHeight(350)
        self.setStyleSheet(DARK_THEME)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

        
        self.current_domain = current_domain
        self.domains = domains or []
        self.refresh_interval = refresh_interval
        self.on_domain_change = on_domain_change
        self.on_interval_change = on_interval_change
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Domain section
        if domains:
            domain_header = QtWidgets.QLabel("Domain Settings")
            domain_header.setObjectName("settings-header")
            layout.addWidget(domain_header)
            
            domain_group = QtWidgets.QGroupBox()
            domain_group.setStyleSheet("""
                QGroupBox {
                    border: 1px solid rgba(255, 255, 255, 0.1);

                }
            """)
            domain_layout = QtWidgets.QVBoxLayout(domain_group)
            
            # Add domain radio buttons
            for domain in domains:
                radio = QtWidgets.QRadioButton(domain)
                radio.setChecked(domain == current_domain)
                radio.toggled.connect(lambda checked, d=domain: self._on_domain_selected(d, checked))
                domain_layout.addWidget(radio)
            
            layout.addWidget(domain_group)
            
            # Add a separator
            separator = QtWidgets.QFrame()
            separator.setObjectName("settings-separator")
            separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
            layout.addWidget(separator)
        
        # Refresh interval section
        refresh_header = QtWidgets.QLabel("Inbox Refresh Interval")
        refresh_header.setObjectName("settings-header")
        layout.addWidget(refresh_header)
        
        refresh_group = QtWidgets.QGroupBox()
        refresh_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid rgba(255, 255, 255, 0.1);

            }
        """)
        refresh_layout = QtWidgets.QVBoxLayout(refresh_group)
        
        # Add interval radio buttons
        intervals = [(1, '1 second'), (5, '5 seconds'), (10, '10 seconds'), 
                    (30, '30 seconds'), (60, '1 minute')]
        
        for value, text in intervals:
            radio = QtWidgets.QRadioButton(text)
            radio.setChecked(value == refresh_interval)
            radio.toggled.connect(lambda checked, v=value: self._on_interval_selected(v, checked))
            refresh_layout.addWidget(radio)
        
        layout.addWidget(refresh_group)
        
        # Add button box for OK
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)
    
    def _on_domain_selected(self, domain, checked):
        if checked and self.on_domain_change:
            self.current_domain = domain
            self.on_domain_change(domain)
    
    def _on_interval_selected(self, value, checked):
        if checked and self.on_interval_change:
            self.refresh_interval = value
            self.on_interval_change(value)

class TempMailApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(500, 400)  # Smaller minimum size
        self.apis: Dict[str, any] = {}  # Store API instances
        self.addresses: Dict[str, Dict] = {}
        self.current_address: Optional[str] = None
        self.refresh_timer = None
        self.unread_counts: Dict[str, int] = {}
        self.current_domain = None
        self.refresh_interval = 3  # Default 3 seconds
        self.message_cache: Dict[str, List[Dict]] = {}  # Cache for messages
        self.recently_updated = set()  # Track addresses with new messages
        self._drag_pos = None
        self._setup_auto_refresh()
        
        # Create dummy card attribute
        self.card = DummyCard()
        
        self._init_ui()
        self._load_config()
        self._load_messages()
        self._setup_auto_refresh()

    def _init_ui(self):
        self.setStyleSheet(DARK_THEME)

        # Main container with compact layout
        container = QtWidgets.QWidget()
        container.setObjectName('main-container')
        main_layout = QtWidgets.QVBoxLayout(container)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Compact toolbar
        self.toolbar = CompactToolbar(self)
        self.toolbar.create_signal.connect(lambda: asyncio.create_task(self._create_address()))
        self.toolbar.settings_signal.connect(self._show_settings_menu)
        main_layout.addWidget(self.toolbar)

        # Stacked pages
        self.stacked = QtWidgets.QStackedWidget()
        main_layout.addWidget(self.stacked, 1)
        self.setCentralWidget(container)

        # Page 0: Address List
        addr_page = QtWidgets.QWidget()
        v0 = QtWidgets.QVBoxLayout(addr_page)
        v0.setContentsMargins(0, 0, 0, 0)
        v0.setSpacing(6)

        self.addr_list = QtWidgets.QListWidget()
        self.addr_list.itemClicked.connect(self._on_addr_selected)
        v0.addWidget(self.addr_list)

        self.stacked.addWidget(addr_page)

        # Page 1: Inbox
        in_page = QtWidgets.QWidget()
        vi = QtWidgets.QVBoxLayout(in_page)
        vi.setContentsMargins(0, 0, 0, 0)
        vi.setSpacing(6)

        # Compact header
        header_layout = QtWidgets.QHBoxLayout()
        back0 = QtWidgets.QPushButton('☚')
        back0.clicked.connect(self._show_home_page)
        header_layout.addWidget(back0)
        
        refresh_inbox_btn = QtWidgets.QPushButton('🗘')
        refresh_inbox_btn.clicked.connect(lambda: asyncio.create_task(self._refresh_messages()))
        header_layout.addWidget(refresh_inbox_btn)
        header_layout.addStretch()
        
        vi.addLayout(header_layout)

        self.msg_list = QtWidgets.QListWidget()
        self.msg_list.itemClicked.connect(self._on_msg_selected)
        vi.addWidget(self.msg_list)

        self.stacked.addWidget(in_page)

        # Page 2: Message View - with the back button in the same place as inbox
        msg_page = QtWidgets.QWidget()
        vm = QtWidgets.QVBoxLayout(msg_page)
        vm.setContentsMargins(0, 0, 0, 0)
        vm.setSpacing(6)

        # Compact header - similar to inbox page
        header_layout = QtWidgets.QHBoxLayout()
        back1 = QtWidgets.QPushButton('☚')
        back1.clicked.connect(self._show_inbox_page)  # Go back to inbox instead of home
        header_layout.addWidget(back1)
        header_layout.addStretch()

        vm.addLayout(header_layout)

        # Then add the tabs without the back button
        self.tabs = QtWidgets.QTabWidget()
        self.html_view = QtWidgets.QTextBrowser()
        self.html_view.setOpenExternalLinks(True)
        self.raw_view = QtWidgets.QTextEdit()
        self.raw_view.setReadOnly(True)
        self.tabs.addTab(self.html_view, 'HTML')
        self.tabs.addTab(self.raw_view, 'Raw')
        vm.addWidget(self.tabs)

        self.stacked.addWidget(msg_page)

        # Compact status bar
        self.statusBar().setStyleSheet('padding: 3px;')

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # record the offset between the window’s top-left and the click
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos is not None:
            # move the window to follow the mouse, keeping that offset
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()

    def _get_api(self, service_key: str):
        """Get or create API instance for a service"""
        if service_key not in self.apis:
            api_class = SERVICE_REGISTRY.get(service_key)
            if api_class:
                self.apis[service_key] = api_class()
        return self.apis.get(service_key)

    def _show_settings_menu(self):
        """Show settings in an enhanced dialog."""
        current_service = self.toolbar.get_selected_service()
        api = self._get_api(current_service)
        
        domains = None
        if api and hasattr(api, 'domains') and api.domains:
            domains = api.domains
            
        dialog = SettingsDialog(
            parent=self,
            current_domain=self.current_domain,
            domains=domains,
            refresh_interval=self.refresh_interval,
            on_domain_change=self._set_domain,
            on_interval_change=self._set_refresh_interval
        )
        
        dialog.exec()

    def _set_domain(self, domain: str):
        """Set the domain for new email addresses."""
        self.current_domain = domain
        self.statusBar().showMessage(f'Domain: {domain}', 3000)

    def _set_refresh_interval(self, value: int):
        """Set the refresh interval."""
        self.refresh_interval = value
        if self.refresh_timer:
            self.refresh_timer.stop()
            self.refresh_timer.start(value * 1000)
        
        # Change message based on interval
        if value == 1:
            msg = f'Refresh: {value} second'
        else:
            msg = f'Refresh: {value} seconds'
            
        self.statusBar().showMessage(msg, 3000)

    async def _create_address(self):
        """Create a new email address using current service."""
        service_key = self.toolbar.get_selected_service()
        api = self._get_api(service_key)
        
        if not api:
            self.statusBar().showMessage(f'Error: Service {service_key} not available', 5000)
            return
        
        try:
            # Create new API instance - no need to close sessions as they're created/closed per method call now
            api_class = type(api)
            api = self.apis[service_key] = api_class()
            
            resp = await api.create_address(self.current_domain)
            addr = resp.get('email')
            token = resp.get('token')
            
            if not addr or not token:
                raise ValueError('Invalid server response')
            
            # Store address with service information and creation time
            self.addresses[addr] = {
                'token': token,
                'messages': [],
                'service': service_key,
                'created_at': time(),  # Add creation timestamp
                'last_updated': time()  # Track last update time
            }
            self.unread_counts[addr] = 0
            self.current_address = addr
            self.message_cache[addr] = []  # Initialize cache for this address
            self._update_address_list()
            self.statusBar().showMessage(f'✓ Created {api.service_name}: {addr}', 3000)
            
        except Exception as e:
            error_msg = f'Error creating email: {str(e)}'
            logging.error(error_msg)
            self.statusBar().showMessage(error_msg, 5000)

    def _setup_auto_refresh(self):
        """Setup automatic refresh timer."""
        self.refresh_timer = QtCore.QTimer()
        self.refresh_timer.timeout.connect(self._auto_refresh_messages)
        self.refresh_timer.start(self.refresh_interval * 1000)

    def _auto_refresh_messages(self):
        """Automatically check for new messages and update timers."""
        asyncio.create_task(self._async_refresh_all())
        
        # Also trigger timer updates for all email items
        for i in range(self.addr_list.count()):
            item = self.addr_list.item(i)
            widget = self.addr_list.itemWidget(item)
            if isinstance(widget, EmailListItem) and widget.timer:
                widget.update_timer()

    async def _async_refresh_all(self):
        """Asynchronously check all addresses for new messages."""
        if not hasattr(self, 'addr_list') or not hasattr(self, 'msg_list'):
            return
            
        # Create a copy of addresses to prevent dictionary size change error
        address_list = list(self.addresses.keys())
        self.recently_updated = set()  # Reset recently updated addresses
        
        for addr in address_list:
            if addr not in self.addresses:
                continue  # Skip if address was removed during iteration
                
            data = self.addresses[addr]
            try:
                service_key = data.get('service', 'guerrillamail')
                api = self._get_api(service_key)
                
                if not api:
                    continue
                
                token = data['token']
                msgs = await api.get_messages(token)
                
                # Cache new messages
                if addr not in self.message_cache:
                    self.message_cache[addr] = []
                
                old_count = len(self.message_cache.get(addr, []))
                
                # Add new messages to cache
                new_messages_added = False
                for msg in msgs:
                    # Check if message already in cache by ID
                    if not any(cached_msg.get('mail_id') == msg.get('mail_id') 
                              for cached_msg in self.message_cache[addr]):
                        self.message_cache[addr].append(msg.copy())
                        new_messages_added = True
                
                # Use cached messages
                cached_msgs = self.message_cache[addr]
                new_count = len(cached_msgs)
                
                self.unread_counts[addr] = new_count
                data['messages'] = cached_msgs
                
                if addr == self.current_address:
                    if hasattr(self, 'msg_list'):
                        self._update_message_list(cached_msgs)
                    if hasattr(self, 'card') and hasattr(self.card, 'update_message_count'):
                        self.card.update_message_count(new_count)
                
                if new_count > old_count:
                    # Mark address as recently updated (for sorting to top)
                    self.recently_updated.add(addr)
                    # Update timestamp for sorting
                    data['last_updated'] = time()
                    # Save messages after each new one arrives
                    self._save_messages()
                    self.statusBar().showMessage(f'📬 New message for {addr}', 5000)
                    
            except Exception as e:
                logging.error(f'Error refreshing {addr}: {e}')
        
        # Update address list to move recently updated addresses to top
        if self.recently_updated:
            self._update_address_list()

    def _show_home_page(self):
        """Navigate to home/addresses page."""
        self.stacked.setCurrentIndex(0)
        
    def _show_inbox_page(self):
        """Navigate to inbox page."""
        self.stacked.setCurrentIndex(1)
        
    def _show_message_page(self):
        """Navigate to message view page."""
        self.stacked.setCurrentIndex(2)

    def _on_addr_selected(self, item: QtWidgets.QListWidgetItem):
        """Handle address selection."""
        widget = self.addr_list.itemWidget(item)
        if isinstance(widget, EmailListItem):
            addr = widget.email
            self.current_address = addr
            self.stacked.setCurrentIndex(1)
            # Show cached messages immediately
            if addr in self.message_cache:
                self._update_message_list(self.message_cache[addr])
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
            if addr in self.message_cache:
                del self.message_cache[addr]
            
            if addr == self.current_address:
                self.current_address = None
                self.msg_list.clear()
            
            self._update_address_list()
            self._save_messages()  # Save after deletion

    def _copy_email(self, email: str):
        """Copy email to clipboard."""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(email)
        self.statusBar().showMessage(f'   🗐 Copied: {email}', 3000)

    def _get_service_expiry(self, service_key: str) -> int:
        """Get the expiration time in seconds for a service."""
        api = self._get_api(service_key)
        if api and hasattr(api, 'expiration_seconds'):
            return api.expiration_seconds
        
        # Default expiration times if the API doesn't have the property
        expiry_map = {
            'guerrillamail': 3600,    # 1 hour
            'mailgw': 600,          # 10 minutes
            'dropmail': 600,         # 10 minutes
            'mailtm': 604800,          # 7 days
            'tempmaillol': 3600       # 1 hour
        }
        return expiry_map.get(service_key, 3600)  # Default to 1 hour if service not found

    def _update_address_list(self):
        """Update the address list with custom widgets, sort with recent emails at top."""
        self.addr_list.clear()
        
        # Sort addresses: recently updated first, then by last_updated time (newest first)
        sorted_addresses = []
        
        # First add recently updated addresses (ones with new messages)
        for addr in self.recently_updated:
            if addr in self.addresses:
                sorted_addresses.append(addr)
        
        # Then add remaining addresses sorted by last_updated time
        remaining = [addr for addr in self.addresses if addr not in self.recently_updated]
        remaining.sort(key=lambda a: self.addresses[a].get('last_updated', 0), reverse=True)
        sorted_addresses.extend(remaining)
        
        # Add all addresses to the list widget
        for addr in sorted_addresses:
            data = self.addresses[addr]
            count = self.unread_counts.get(addr, 0)
            service_key = data.get('service', 'guerrillamail')
            api = self._get_api(service_key)
            service_name = api.service_name if api else service_key
            
            # Get creation time and expiry period
            created_at = data.get('created_at')
            expiry_seconds = self._get_service_expiry(service_key)
            
            item = QtWidgets.QListWidgetItem()
            item.setSizeHint(QtCore.QSize(0, 46))  # Slightly taller for service badge
            
            widget = EmailListItem(addr, count, service_name, created_at, expiry_seconds)
            widget.copy_signal.connect(self._copy_email)
            widget.delete_signal.connect(self._delete_address)
            
            self.addr_list.addItem(item)
            self.addr_list.setItemWidget(item, widget)

    def _update_message_list(self, messages: List[Dict]):
        """Update the message list."""
        if not hasattr(self, 'msg_list'):
            return
            
        self.msg_list.clear()
        for msg in reversed(messages):
            subj = msg.get('subject', 'No Subject')
            sender = msg.get('mail_from', 'Unknown')
            date = self._fmt(ts=msg.get('mail_date'))
            
            display_text = f'{subj}\nFrom: {sender} • {date}'
            item = QtWidgets.QListWidgetItem(display_text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, msg.get('mail_id'))
            
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            
            self.msg_list.addItem(item)

    def _fmt(self, ts):
        """Format timestamp to readable date."""
        try:
            if isinstance(ts, str):
                # Try to parse as timestamp first
                try:
                    ts_int = int(ts)
                    dt = datetime.fromtimestamp(ts_int)
                    return dt.strftime('%Y-%m-%d %H:%M')
                except (ValueError, TypeError):
                    # If it's not a timestamp, return as is if it looks like a date
                    if ts and len(ts) > 5:  # Basic check to see if it's a date-like string
                        return ts
            elif isinstance(ts, int):
                dt = datetime.fromtimestamp(ts)
                return dt.strftime('%Y-%m-%d %H:%M')
            elif ts is None:
                return ''
            
            # Fallback
            return str(ts) if ts is not None else ''
        except Exception as e:
            logging.error(f"Error formatting date: {e}")
            return str(ts) if ts is not None else ''

    def _format_size(self, size):
        """Format email size in human-readable format."""
        try:
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

    async def _show_message(self, mail_id: str):
        """Display a specific message from cache or fetch it."""
        try:
            data = self.addresses[self.current_address]
            service_key = data.get('service', 'guerrillamail')
            api = self._get_api(service_key)
            
            if not api:
                raise Exception(f'Service {service_key} not available')
            
            # First try to find message in cache
            cached_msg = None
            if self.current_address in self.message_cache:
                for msg in self.message_cache[self.current_address]:
                    if msg.get('mail_id') == mail_id:
                        cached_msg = msg
                        break
            
            # If not found in cache, fetch it
            if cached_msg is None:
                token = data['token']
                cached_msg = await api.fetch_message(token, mail_id)
                # Save to cache
                if 'full_content' not in cached_msg:
                    cached_msg['full_content'] = True  # Mark as fully loaded
                    # Add to message cache if not already there
                    if self.current_address in self.message_cache:
                        self.message_cache[self.current_address].append(cached_msg)
                    self._save_messages()
            
            # If cached message doesn't have body content, fetch it again
            if not cached_msg.get('mail_body'):
                token = data['token']
                fresh_msg = await api.fetch_message(token, mail_id)
                if fresh_msg.get('mail_body'):
                    cached_msg['mail_body'] = fresh_msg['mail_body']
                    # Also update other fields if present
                    for key in ['mail_date', 'mail_size']:
                        if key in fresh_msg and fresh_msg[key]:
                            cached_msg[key] = fresh_msg[key]
                    self._save_messages()
            
            html = cached_msg.get('mail_body', '')
            
            # Ensure html is a string
            if not isinstance(html, str):
                if isinstance(html, list) and len(html) > 0:
                    # If it's a list, join the elements
                    html = '\n'.join([str(item) for item in html])
                else:
                    # Convert to string or use empty string
                    html = str(html) if html else ''
            
            # For GuerrillaMailAPI, we need to handle its specific format
            if service_key == 'guerrillamail':
                # GuerrillaMailAPI returns body in 'mail_body' field
                if not html and 'body' in cached_msg:
                    html = cached_msg.get('body', '')
                # Also check 'body_html'
                if not html and 'body_html' in cached_msg:
                    html = cached_msg.get('body_html', '')
            
            # For Mail services, ensure proper HTML formatting
            if service_key in ['mailgw', 'mailtm', 'dropmail'] and html:
                # If it's not already HTML, convert to HTML
                if not html.strip().startswith('<'):
                    html = html.replace('\n', '<br>')
                    html = f'<div style="font-family: Arial, sans-serif; color: white;">{html}</div>'
            
            # Make links clickable by ensuring proper URL formatting
            if html:
                # Handle links without protocol (only if html is a string)
                html = html.replace('href="//', 'href="https://')
                html = html.replace('href="www.', 'href="http://www.')
                
                # Convert plain text links to clickable links
                if 'http://' in html or 'https://' in html:
                    # Find URLs in text and make them into proper links
                    url_pattern = r'(?<!href=")((https?://|www\.)[^\s<>"]+)'
                    html = re.sub(url_pattern, r'<a href="\1">\1</a>', html)
                    # Fix links that don't start with http
                    html = re.sub(r'<a href="www\.', r'<a href="http://www.', html)
            
            # Format metadata for message display
            meta = f"""
            <div style="margin-bottom: 12px;">
                <h3 style="margin: 8px 0; color: white;">📧 {cached_msg.get('subject', 'No Subject')}</h3>
                <p style="margin: 6px 0; color: rgba(255,255,255,0.9);">
                    <strong>From:</strong> {cached_msg.get('mail_from', 'Unknown')}<br>
                    <strong>Date:</strong> {self._fmt(ts=cached_msg.get('mail_date', ''))}<br>
                    <strong>Size:</strong> {self._format_size(cached_msg.get('mail_size', 0))}<br>
                    <strong>Service:</strong> {api.service_name}
                </p>
                <hr style="border-color: #333;">
            </div>
            """
            
            # Ensure HTML content has proper styling for dark mode
            if html:
                # Add base styles for dark mode compatibility
                style_tag = """
                <style>
                    body { color: white; background: transparent; }
                    a { color: #1f97b6; }
                    a:hover { color: #17a2d8; }
                    pre, code { background-color: #202428; padding: 4px; border-radius: 3px; }
                </style>
                """
                html = style_tag + html
            
            self.html_view.setHtml(meta + html)
            self.raw_view.setPlainText(json.dumps(cached_msg, indent=2))
        except Exception as e:
            error_msg = f'Error loading message: {str(e)}'
            logging.error(error_msg)
            logging.error(f"Exception details: {e}")
            import traceback
            logging.error(traceback.format_exc())
            self.html_view.setHtml(f'<p style="color: #dc3545;">{error_msg}</p>')
            self.raw_view.clear()
            self.statusBar().showMessage(error_msg, 5000)

    async def _refresh_messages(self):
        """Refresh messages for current address."""
        if not self.current_address:
            return
        try:
            data = self.addresses[self.current_address]
            service_key = data.get('service', 'guerrillamail')
            api = self._get_api(service_key)
            
            if not api:
                raise Exception(f'Service {service_key} not available')
            
            token = data['token']
            msgs = await api.get_messages(token)
            
            # Update cache
            if self.current_address not in self.message_cache:
                self.message_cache[self.current_address] = []
                
            old_count = len(self.message_cache.get(self.current_address, []))
            
            # Add new messages to cache
            has_new_messages = False
            for msg in msgs:
                if not any(cached_msg.get('mail_id') == msg.get('mail_id') 
                          for cached_msg in self.message_cache[self.current_address]):
                    self.message_cache[self.current_address].append(msg.copy())
                    has_new_messages = True
            
            # Use cached messages
            cached_msgs = self.message_cache[self.current_address]
            new_count = len(cached_msgs)
            data['messages'] = cached_msgs
            self.unread_counts[self.current_address] = new_count
            self._update_message_list(cached_msgs)
            
            # If we have new messages, update last_updated time
            if has_new_messages:
                data['last_updated'] = time()
                # Add to recently updated set
                self.recently_updated.add(self.current_address)
                
            self._save_messages()  # Save after refresh
            self.statusBar().showMessage('📬 Inbox refreshed                                                              Developed by: github.com/zebbern', 2000)
        except Exception as e:
            error_msg = f'Error refreshing messages: {str(e)}'
            logging.error(error_msg)
            self.statusBar().showMessage(error_msg, 5000)

    def _load_config(self):
        """Load saved configuration."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    data = json.load(f)
                    self.addresses = data.get('addresses', {})
                    self.unread_counts = data.get('unread_counts', {})
                    
                    # Ensure all addresses have a last_updated timestamp
                    for addr, data in self.addresses.items():
                        if 'last_updated' not in data:
                            data['last_updated'] = data.get('created_at', time())
                    
                    if self.addresses:
                        self.current_address = next(iter(self.addresses))
                        if hasattr(self, 'addr_list'):
                            self._update_address_list()
            except Exception as e:
                logging.error(e)

    def _load_messages(self):
        """Load cached messages from file."""
        if MESSAGES_FILE.exists():
            try:
                with open(MESSAGES_FILE) as f:
                    self.message_cache = json.load(f)
            except Exception as e:
                logging.error(f"Error loading messages: {e}")
                self.message_cache = {}

    def _save_messages(self):
        """Save cached messages to file."""
        try:
            with open(MESSAGES_FILE, 'w') as f:
                json.dump(self.message_cache, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving messages: {e}")

    def closeEvent(self, event):
        """Save configuration on close."""
        try:
            config_data = {
                'addresses': self.addresses,
                'unread_counts': self.unread_counts
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            # Save messages
            self._save_messages()
        except Exception as e:
            logging.error(e)
        
        # No need to close sessions as they're created and closed per method now
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
