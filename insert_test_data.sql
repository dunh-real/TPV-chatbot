-- ============================================================
-- TEST DATA SCRIPT cho erps database
-- Chạy theo thứ tự từ trên xuống (dependency order)
-- ============================================================

-- 1. Dms_WorkDepartment
INSERT INTO Dms_WorkDepartment (TenantId, ParentId, Code, DepartmentCode, DisplayName, Describe, CreationTime, IsDeleted)
VALUES
(2, NULL, 'DEPT001', 'IT',  N'Phong Cong nghe thong tin', N'Phong IT', GETDATE(), 0),
(2, NULL, 'DEPT002', 'HR',  N'Phong Nhan su',             N'Phong HR', GETDATE(), 0),
(2, NULL, 'DEPT003', 'KT',  N'Phong Ke toan',             N'Phong KT', GETDATE(), 0),
(2, NULL, 'DEPT004', 'DEV', N'Nhom Phat trien phan mem',  N'Dev team', GETDATE(), 0);

-- 2. Dms_WorkPosition
INSERT INTO Dms_WorkPosition (TenantId, Code, Name, IsManager, [Order], IsDefault, IsActive, CreationTime, IsDeleted)
VALUES
(2, 'POS001', N'Giam doc',       1, 1, 0, 1, GETDATE(), 0),
(2, 'POS002', N'Truong phong',   1, 2, 0, 1, GETDATE(), 0),
(2, 'POS003', N'Nhan vien',      0, 3, 1, 1, GETDATE(), 0),
(2, 'POS004', N'Lap trinh vien', 0, 4, 0, 1, GETDATE(), 0),
(2, 'POS005', N'Ke toan vien',   0, 5, 0, 1, GETDATE(), 0);

-- 3. Dms_Employee
-- Chay query nay truoc de lay Id cua WorkDepartment va WorkPosition vua insert
-- SELECT Id, DepartmentCode FROM Dms_WorkDepartment WHERE TenantId = 2
-- SELECT Id, Code FROM Dms_WorkPosition WHERE TenantId = 2
INSERT INTO Dms_Employee (TenantId, Code, RoleId, FullName, DoB, Gender, Email, Phone, WorkDepartmentId, WorkPositionId, CreationTime, IsDeleted)
VALUES
(2, 'EMP002', 1, N'Nguyen Van An',  '1990-03-15', 1, N'an.nguyen@company.com',   '0901234567', 1, 4, GETDATE(), 0),
(2, 'EMP003', 1, N'Tran Thi Binh',  '1992-07-20', 0, N'binh.tran@company.com',   '0912345678', 2, 2, GETDATE(), 0),
(2, 'EMP004', 1, N'Le Minh Cuong',  '1988-11-05', 1, N'cuong.le@company.com',    '0923456789', 1, 4, GETDATE(), 0),
(2, 'EMP005', 1, N'Pham Thi Dung',  '1995-04-12', 0, N'dung.pham@company.com',   '0934567890', 3, 5, GETDATE(), 0),
(2, 'EMP006', 1, N'Hoang Van Em',   '1991-09-28', 1, N'em.hoang@company.com',    '0945678901', 2, 3, GETDATE(), 0),
(2, 'EMP007', 1, N'Vu Thi Phuong',  '1993-01-17', 0, N'phuong.vu@company.com',   '0956789012', 1, 4, GETDATE(), 0),
(2, 'EMP008', 1, N'Dang Van Giang', '1987-06-30', 1, N'giang.dang@company.com',  '0967890123', 3, 5, GETDATE(), 0),
(2, 'EMP009', 1, N'Bui Thi Hoa',    '1996-12-08', 0, N'hoa.bui@company.com',     '0978901234', 2, 3, GETDATE(), 0),
(2, 'EMP010', 1, N'Ngo Van Inh',    '1989-08-22', 1, N'inh.ngo@company.com',     '0989012345', 1, 1, GETDATE(), 0);

-- 4. Hrm_WorkShift
INSERT INTO Hrm_WorkShift (TenantId, Code, Name, StartTime, EndTime, IsOvernight, IsActive, CreationTime, IsDeleted)
VALUES
(2, 'CA001', N'Ca sang',       '2024-01-01 08:00:00', '2024-01-01 12:00:00', 0, 1, GETDATE(), 0),
(2, 'CA002', N'Ca chieu',      '2024-01-01 13:00:00', '2024-01-01 17:00:00', 0, 1, GETDATE(), 0),
(2, 'CA003', N'Ca hanh chinh', '2024-01-01 08:00:00', '2024-01-01 17:00:00', 0, 1, GETDATE(), 0);

-- 5. Hrm_Attendancel (NV 2-6 cham hom nay, NV 7-10 khong cham hom nay)
DECLARE @today datetime = CAST(CAST(GETDATE() AS DATE) AS datetime)
DECLARE @yday1 datetime = DATEADD(DAY, -1, @today)
DECLARE @yday2 datetime = DATEADD(DAY, -2, @today)

INSERT INTO Hrm_Attendancel (TenantId, EmployeeId, Date, CheckInTime, CheckOutTime, VerifyMethod, Type, CreationTime, IsDeleted)
VALUES
(2, 2,  @today, DATEADD(HOUR, 8,  @today), DATEADD(HOUR, 17, @today), 1, 1, GETDATE(), 0),
(2, 3,  @today, DATEADD(HOUR, 8,  @today), DATEADD(HOUR, 17, @today), 1, 1, GETDATE(), 0),
(2, 4,  @today, DATEADD(HOUR, 8,  @today), NULL,                       1, 1, GETDATE(), 0),
(2, 5,  @today, DATEADD(HOUR, 8,  @today), DATEADD(HOUR, 17, @today), 1, 1, GETDATE(), 0),
(2, 6,  @today, DATEADD(HOUR, 9,  @today), DATEADD(HOUR, 18, @today), 1, 1, GETDATE(), 0),
(2, 7,  @yday1, DATEADD(HOUR, 8,  @yday1), DATEADD(HOUR, 17, @yday1), 1, 1, GETDATE(), 0),
(2, 8,  @yday1, DATEADD(HOUR, 8,  @yday1), DATEADD(HOUR, 17, @yday1), 1, 1, GETDATE(), 0),
(2, 9,  @yday2, DATEADD(HOUR, 8,  @yday2), DATEADD(HOUR, 17, @yday2), 1, 1, GETDATE(), 0),
(2, 10, @yday2, DATEADD(HOUR, 8,  @yday2), DATEADD(HOUR, 17, @yday2), 1, 1, GETDATE(), 0);

-- 6. Hrm_LeaveRequest (Status: 0=cho duyet, 1=da duyet, 2=tu choi)
INSERT INTO Hrm_LeaveRequest (TenantId, EmployeeId, StartDate, EndDate, LeaveType, Reason, Status, IsPaidLeave, CreationTime, IsDeleted)
VALUES
(2, 1, DATEADD(DAY, 2,  GETDATE()), DATEADD(DAY, 3,  GETDATE()), 1, N'Viec gia dinh',    0, 1, GETDATE(), 0),
(2, 3, DATEADD(DAY, 5,  GETDATE()), DATEADD(DAY, 7,  GETDATE()), 2, N'Nghi phep nam',    0, 1, GETDATE(), 0),
(2, 7, DATEADD(DAY, 1,  GETDATE()), DATEADD(DAY, 1,  GETDATE()), 1, N'Kham benh',        0, 0, GETDATE(), 0),
(2, 2, DATEADD(DAY, -5, GETDATE()), DATEADD(DAY, -3, GETDATE()), 1, N'Nghi phep',        1, 1, GETDATE(), 0),
(2, 5, DATEADD(DAY, -2, GETDATE()), DATEADD(DAY, -2, GETDATE()), 3, N'Viec ca nhan',     2, 0, GETDATE(), 0),
(2, 8, DATEADD(DAY, 3,  GETDATE()), DATEADD(DAY, 5,  GETDATE()), 2, N'Du lich gia dinh', 0, 1, GETDATE(), 0);

-- 7. Rcm_RecruitmentPlan
INSERT INTO Rcm_RecruitmentPlan (TenantId, Code, Name, StartDate, EndDate, Status, DepartmentId, CreationTime, IsDeleted)
VALUES
(2, 'RCP001', N'Tuyen dung IT Q1 2025', '2025-01-01', '2025-03-31', 1, 1, GETDATE(), 0),
(2, 'RCP002', N'Tuyen dung KT Q2 2025', '2025-04-01', '2025-06-30', 0, 3, GETDATE(), 0),
(2, 'RCP003', N'Tuyen dung HR Q1 2025', '2025-01-15', '2025-02-28', 2, 2, GETDATE(), 0);

-- 10. Hrm_JobPosting
INSERT INTO Hrm_JobPosting (TenantId, RecruitmentPlanId, WorkPositionId, Code, Name, Description, Requirements, SalaryRange, CreatedDate, IsActive, CreationTime, IsDeleted)
VALUES
(2, 1, 4, 'JP001', N'Lap trinh vien Backend .NET',   N'Phat trien API va he thong backend',   N'2+ nam .NET, SQL Server, RESTful API',    N'15-25 trieu', GETDATE(), 1, GETDATE(), 0),
(2, 1, 4, 'JP002', N'Lap trinh vien Frontend React', N'Phat trien giao dien nguoi dung',       N'2+ nam React, TypeScript, CSS',           N'12-20 trieu', GETDATE(), 1, GETDATE(), 0),
(2, 2, 5, 'JP003', N'Ke toan tong hop',              N'Quan ly so sach ke toan toan cong ty', N'Tot nghiep ke toan, 3+ nam kinh nghiem',  N'10-15 trieu', GETDATE(), 1, GETDATE(), 0),
(2, 3, 3, 'JP004', N'Chuyen vien nhan su',            N'Tuyen dung va quan ly nhan su',        N'Tot nghiep quan tri nhan luc',            N'8-12 trieu',  GETDATE(), 0, GETDATE(), 0);



Dưới đây là bộ câu hỏi test bao phủ các workspace chính:

HR - Nhân viên/Phòng ban

Danh sách nhân viên đang làm việc?

Nhân viên nào chưa chấm công hôm nay?

Phòng IT có bao nhiêu nhân viên?

Nhân viên nào sinh năm 1990?

Danh sách nhân viên phòng Nhân sự?

HR - Chấm công
6. Hôm nay có bao nhiêu người đã chấm công?
7. Nhân viên nào check-in muộn hôm nay (sau 8h30)?
8. Nhân viên nào chưa check-out hôm nay?

HR - Nghỉ phép
9. Có bao nhiêu đơn xin nghỉ phép đang chờ duyệt?
10. Danh sách đơn nghỉ phép đã được duyệt?
11. Nhân viên nào có đơn nghỉ phép trong tuần tới?

Recruitment - Tuyển dụng
12. Danh sách tin tuyển dụng đang mở?
13. Có bao nhiêu kế hoạch tuyển dụng đang thực hiện?
14. Tin tuyển dụng nào có mức lương cao nhất?

Câu hỏi phức tạp (JOIN nhiều bảng)
15. Nhân viên nào vừa có đơn nghỉ phép vừa chưa chấm công hôm nay?
16. Phòng nào có nhiều nhân viên nhất?
17. Nhân viên nào là trưởng phòng?