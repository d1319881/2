import unittest
from datetime import datetime, timedelta
from flask import session
from app import create_app
from app.models import db
from app.models.user import User
from app.models.leave import Leave
from app.models.shift import Shift

class TestLeaveFlow(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'SECRET_KEY': 'test-secret-key'
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Seed users
        self.manager = User.create('boss', 'bossPass', 'Boss Manager', 'manager')
        self.staff = User.create('worker', 'workerPass', 'Worker Staff', 'staff')

        # Seed shift for worker (today 10:00 - 18:00)
        self.today = datetime.utcnow().date()
        self.shift_start = datetime.combine(self.today, datetime.min.time()) + timedelta(hours=10)
        self.shift_end = datetime.combine(self.today, datetime.min.time()) + timedelta(hours=18)
        self.shift = Shift.create('早班', self.shift_start, self.shift_end, staff_id=self.staff.id, is_draft=False)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_leave_apply_success(self):
        # Login staff
        self.client.post('/auth/login', data={'username': 'worker', 'password': 'workerPass'})

        # Apply for leave (overlapping with shift: 09:00 - 18:00)
        leave_start = datetime.combine(self.today, datetime.min.time()) + timedelta(hours=9)
        leave_end = datetime.combine(self.today, datetime.min.time()) + timedelta(hours=18)

        response = self.client.post('/leave/apply', data={
            'leave_type': 'Personal',
            'start_time': leave_start.strftime('%Y-%m-%dT%H:%M'),
            'end_time': leave_end.strftime('%Y-%m-%dT%H:%M'),
            'reason': 'Doctor appointment'
        })
        self.assertEqual(response.status_code, 302)

        # Check Leave in DB
        leave = Leave.query.filter_by(staff_id=self.staff.id).first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.status, 'Pending')

        # Check Shift is still assigned (only Pending)
        db.session.refresh(self.shift)
        self.assertEqual(self.shift.staff_id, self.staff.id)

    def test_leave_approve_clears_shift(self):
        # Create pending leave
        leave_start = datetime.combine(self.today, datetime.min.time()) + timedelta(hours=9)
        leave_end = datetime.combine(self.today, datetime.min.time()) + timedelta(hours=18)
        leave = Leave.create(self.staff.id, leave_start, leave_end, 'Personal', 'Appointment')

        # Login manager
        self.client.post('/auth/login', data={'username': 'boss', 'password': 'bossPass'})

        # Approve Leave
        response = self.client.post(f'/leave/review/{leave.id}/approve')
        self.assertEqual(response.status_code, 302)

        # Check status changed
        db.session.refresh(leave)
        self.assertEqual(leave.status, 'Approved')

        # Check Shift is now empty (staff_id = None)
        db.session.refresh(self.shift)
        self.assertIsNone(self.shift.staff_id)

    def test_leave_reject_keeps_shift(self):
        # Create pending leave
        leave_start = datetime.combine(self.today, datetime.min.time()) + timedelta(hours=9)
        leave_end = datetime.combine(self.today, datetime.min.time()) + timedelta(hours=18)
        leave = Leave.create(self.staff.id, leave_start, leave_end, 'Personal', 'Appointment')

        # Login manager
        self.client.post('/auth/login', data={'username': 'boss', 'password': 'bossPass'})

        # Reject Leave
        response = self.client.post(f'/leave/review/{leave.id}/reject', data={'comment': 'No staffing today'})
        self.assertEqual(response.status_code, 302)

        # Check status changed
        db.session.refresh(leave)
        self.assertEqual(leave.status, 'Rejected')
        self.assertIn('No staffing today', leave.reason)

        # Check Shift is still assigned to worker
        db.session.refresh(self.shift)
        self.assertEqual(self.shift.staff_id, self.staff.id)

    def test_shift_swap(self):
        # Login staff
        self.client.post('/auth/login', data={'username': 'worker', 'password': 'workerPass'})

        # Post swap for shift
        response = self.client.post('/shift/swap/post', data={'shift_id': str(self.shift.id)})
        self.assertEqual(response.status_code, 302)

        # Check shift has been released (staff_id = None)
        db.session.refresh(self.shift)
        self.assertIsNone(self.shift.staff_id)

if __name__ == '__main__':
    unittest.main()
