-- 自動打工排班最佳化系統 - SQLite Schema DDL
-- 儲存路徑: 初始化專案骨架/database/schema.sql

-- 啟用外鍵約束
PRAGMA foreign_keys = ON;

-- 1. 使用者資料表 (店長與員工)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('manager', 'staff')),
    max_weekly_hours REAL NOT NULL DEFAULT 40.0,
    max_daily_hours REAL NOT NULL DEFAULT 8.0,
    preferences TEXT, -- 儲存 JSON 字串如: {"unavailable_days": [0, 6], "preferred_shifts": ["早班"]}
    is_deleted BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. 班表記錄表 (排班表)
CREATE TABLE IF NOT EXISTS shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    staff_id INTEGER, -- 指派員工，為 NULL 代表空班/缺工
    is_draft BOOLEAN NOT NULL DEFAULT 1, -- 是否為草稿
    is_deleted BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (staff_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 3. 請假申請表
CREATE TABLE IF NOT EXISTS leaves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    leave_type TEXT NOT NULL, -- e.g., 'Vacation', 'Sick', 'Personal'
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected')),
    reviewed_by INTEGER,
    reviewed_at DATETIME,
    is_deleted BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (staff_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
);

-- 4. 操作日誌表 (Audit Logs)
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    details TEXT, -- JSON 格式的詳細變動內容
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 建立索引以優化排班與查詢效能
CREATE INDEX IF NOT EXISTS idx_shifts_time ON shifts(start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_shifts_staff ON shifts(staff_id);
CREATE INDEX IF NOT EXISTS idx_leaves_staff ON leaves(staff_id);
CREATE INDEX IF NOT EXISTS idx_leaves_time ON leaves(start_time, end_time);
