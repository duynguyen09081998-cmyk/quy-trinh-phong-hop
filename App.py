import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from contextlib import contextmanager

# Cấu hình trang Web
st.set_page_config(page_title="Đăng ký Phòng Họp - V14", layout="wide")

# --- HÀM KẾT NỐI DATABASE (SQLite trực tiếp trên Cloud) ---
def init_db():
    conn = sqlite3.connect("room_booking_cloud.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_name TEXT NOT NULL,
            requester TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'Pending',
            reject_reason TEXT
        )
    """)
    conn.commit()
    conn.close()

# Khởi tạo database ngay khi ứng dụng web chạy
init_db()

@contextmanager
def get_db():
    conn = sqlite3.connect("room_booking_cloud.db")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# --- GIAO DIỆN CHÍNH ---
st.title("🏢 Hệ thống Quản lý & Phê duyệt Phòng họp (Bản Cloud V14)")
st.markdown("---")

tab1, tab2 = st.tabs(["🙋‍♂️ Dành cho Nhân viên (Đặt phòng)", "👑 Dành cho Quản lý (Phê duyệt)"])

# ==========================================
# TAB 1: NHÂN VIÊN ĐẶT PHÒNG
# ==========================================
with tab1:
    st.header("Tạo yêu cầu đăng ký phòng họp")
    
    with st.form("booking_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            room_name = st.selectbox("Chọn phòng họp", ["Phòng họp số 1 (Tầng 1)", "Phòng họp Lớn (Tầng 2)", "Phòng Brainstorm (Tầng 3)"])
            requester = st.text_input("Họ và tên người đặt", placeholder="Ví dụ: Nguyễn Văn A")
            booking_date = st.date_input("Chọn ngày họp", min_value=datetime.today())
        with col2:
            start_time = st.time_input("Giờ bắt đầu")
            end_time = st.time_input("Giờ kết thúc")
            reason = st.text_area("Lý do sử dụng phòng", placeholder="Ví dụ: Họp phòng Kinh doanh")
            
        submit_btn = st.form_submit_button("Gửi yêu cầu phê duyệt")
        
        if submit_btn:
            if not requester:
                st.error("Vui lòng nhập tên người đặt phòng!")
            elif start_time >= end_time:
                st.error("Giờ kết thúc phải lớn hơn giờ bắt đầu!")
            else:
                s_time = start_time.strftime("%H:%M")
                e_time = end_time.strftime("%H:%M")
                d_date = str(booking_date)
                
                with get_db() as db:
                    cursor = db.cursor()
                    # Kiểm tra trùng lịch
                    cursor.execute("""
                        SELECT * FROM bookings 
                        WHERE room_name = ? AND booking_date = ? AND status = 'Approved'
                          AND NOT (end_time <= ? OR start_time >= ?)
                    """, (room_name, d_date, s_time, e_time))
                    
                    if cursor.fetchone():
                        st.error("Phòng họp đã có người đặt và duyệt trong khung giờ này!")
                    else:
                        # Lưu vào db
                        cursor.execute("""
                            INSERT INTO bookings (room_name, requester, booking_date, start_time, end_time, reason)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (room_name, requester, d_date, s_time, e_time, reason))
                        db.commit()
                        st.success("Gửi yêu cầu đăng ký thành công! Vui lòng chờ phê duyệt.")

# ==========================================
# TAB 2: QUẢN LÝ PHÊ DUYỆT
# ==========================================
with tab2:
    st.header("Danh sách đơn đăng ký chờ xử lý")
    
    if st.button("🔄 Tải lại danh sách"):
        st.rerun()
        
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("SELECT * FROM bookings WHERE status = 'Pending'")
        rows = cursor.fetchall()
        
        if rows:
            bookings_list = [dict(row) for row in rows]
            df = pd.DataFrame(bookings_list)
            df = df[["id", "room_name", "requester", "booking_date", "start_time", "end_time", "reason"]]
            st.dataframe(df, use_container_width=True)
            
            st.markdown("---")
            st.subheader("Thực hiện phê duyệt đơn")
            
            with st.form("approval_form"):
                col_id, col_act, col_app = st.columns([1, 2, 2])
                with col_id:
                    booking_id = st.number_input("Nhập ID đơn muốn duyệt", min_value=1, step=1)
                with col_act:
                    action = st.selectbox("Hành động", ["Approved", "Rejected"], format_func=lambda x: "Duyệt (Approved)" if x=="Approved" else "Từ chối (Rejected)")
                with col_app:
                    approver = st.text_input("Tên người duyệt", value="Sếp Tổng")
                    
                reject_reason = st.text_input("Lý do từ chối (Nếu có)")
                btn_approve = st.form_submit_button("Xác nhận phê duyệt")
                
                if btn_approve:
                    cursor.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
                    current_booking = cursor.fetchone()
                    
                    if not current_booking:
                        st.error("Không tìm thấy đơn đăng ký này.")
                    elif current_booking["status"] != "Pending":
                        st.error("Đơn này đã được xử lý rồi.")
                    else:
                        if action == "Approved":
                            # Kiểm tra lại trùng lịch phút chót
                            cursor.execute("""
                                SELECT * FROM bookings 
                                WHERE room_name = ? AND booking_date = ? AND status = 'Approved'
                                  AND NOT (end_time <= ? OR start_time >= ?)
                            """, (current_booking["room_name"], current_booking["booking_date"], current_booking["start_time"], current_booking["end_time"]))
                            
                            if cursor.fetchone():
                                st.error("Không thể duyệt vì đã có đơn khác trùng giờ được duyệt trước!")
                            else:
                                cursor.execute("UPDATE bookings SET status = 'Approved' WHERE id = ?", (booking_id,))
                                db.commit()
                                st.success(f"Đơn số {booking_id} đã ĐƯỢC DUYỆT.")
                                st.rerun()
                        else:
                            cursor.execute("UPDATE bookings SET status = 'Rejected', reject_reason = ? WHERE id = ?", (reject_reason, booking_id))
                            db.commit()
                            st.success(f"Đơn số {booking_id} đã BỊ TỪ CHỐI.")
                            st.rerun()
        else:
            st.info("Hiện tại không có đơn nào đang chờ phê duyệt.")
# ==========================================
# KHU VỰC CHUNG: LỊCH SỬ & TRẠNG THÁI PHÒNG HỌP
# ==========================================
st.markdown("---")
st.header("🗓️ Trạng thái đặt phòng thực tế (Tất cả các Đơn)")

# Bộ lọc nhanh trạng thái để người dùng dễ nhìn
status_filter = st.radio(
    "Lọc theo trạng thái:", 
    ["Tất cả", "Đã duyệt (Approved)", "Chờ duyệt (Pending)", "Bị từ chối (Rejected)"], 
    horizontal=True
)

# Chuyển đổi lựa chọn tiếng Việt sang giá trị lưu trong Database
mapping = {
    "Tất cả": None,
    "Đã duyệt (Approved)": "Approved",
    "Chờ duyệt (Pending)": "Pending",
    "Bị từ chối (Rejected)": "Rejected"
}

with get_db() as db:
    cursor = db.cursor()
    selected_status = mapping[status_filter]
    
    if selected_status:
        cursor.execute("SELECT * FROM bookings WHERE status = ? ORDER BY id DESC", (selected_status,))
    else:
        cursor.execute("SELECT * FROM bookings ORDER BY id DESC")
        
    all_rows = cursor.fetchall()
    
    if all_rows:
        # Chuyển dữ liệu thành bảng hiển thị công khai
        full_list = [dict(row) for row in all_rows]
        df_all = pd.DataFrame(full_list)
        
        # Định nghĩa lại tên cột hiển thị cho người dùng phổ thông dễ đọc
        df_all = df_all.rename(columns={
            "id": "Mã Đơn",
            "room_name": "Tên Phòng",
            "requester": "Người Đặt",
            "booking_date": "Ngày Họp",
            "start_time": "Bắt Đầu",
            "end_time": "Kết Thúc",
            "reason": "Lý Do Họp",
            "status": "Trạng Thái",
            "reject_reason": "Lý Do Từ Chối (Nếu có)"
        })
        
        # Hiển thị bảng dạng theo dõi trực quan
        st.dataframe(df_all, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có dữ liệu đơn đăng ký nào phù hợp với bộ lọc này.")