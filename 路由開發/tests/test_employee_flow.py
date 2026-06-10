import unittest
from flask import session
from app import create_app
from app.models import db
from app.models.user import User

class TestEmployeeFlow(unittest.TestCase):
    def setUp(self):
        # Configure app for testing with in-memory database
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

        # Create manager and staff users
        self.manager = User.create('manager_user', 'managerpass', 'Boss Manager', 'manager')
        self.staff = User.create('staff_user', 'staffpass', 'Regular Staff', 'staff')

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_employee_management_accessible_by_manager(self):
        # Log in as manager
        self.client.post('/auth/login', data={'username': 'manager_user', 'password': 'managerpass'})
        
        response = self.client.get('/employees')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'manager_user', response.data)
        self.assertIn(b'staff_user', response.data)

    def test_employee_management_restricted_for_staff(self):
        # Log in as staff
        self.client.post('/auth/login', data={'username': 'staff_user', 'password': 'staffpass'})
        
        response = self.client.get('/employees')
        # Should redirect back to index (302)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/'))

    def test_add_employee_success(self):
        self.client.post('/auth/login', data={'username': 'manager_user', 'password': 'managerpass'})
        
        response = self.client.post('/employees/add', data={
            'username': 'new_guy',
            'password': 'password123',
            'name': 'New Guy',
            'role': 'staff',
            'max_weekly_hours': '35.0',
            'max_daily_hours': '7.5'
        })
        self.assertEqual(response.status_code, 302)
        
        # Verify user created in DB
        user = User.query.filter_by(username='new_guy').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.name, 'New Guy')
        self.assertEqual(user.max_weekly_hours, 35.0)
        self.assertEqual(user.max_daily_hours, 7.5)

    def test_update_employee_success(self):
        self.client.post('/auth/login', data={'username': 'manager_user', 'password': 'managerpass'})
        
        response = self.client.post(f'/employees/{self.staff.id}/update', data={
            'name': 'Updated Name',
            'role': 'manager',
            'max_weekly_hours': '25.0',
            'max_daily_hours': '6.0'
        })
        self.assertEqual(response.status_code, 302)
        
        # Verify user updated in DB
        db.session.refresh(self.staff)
        self.assertEqual(self.staff.name, 'Updated Name')
        self.assertEqual(self.staff.role, 'manager')
        self.assertEqual(self.staff.max_weekly_hours, 25.0)
        self.assertEqual(self.staff.max_daily_hours, 6.0)

    def test_delete_employee_success(self):
        self.client.post('/auth/login', data={'username': 'manager_user', 'password': 'managerpass'})
        
        response = self.client.post(f'/employees/{self.staff.id}/delete')
        self.assertEqual(response.status_code, 302)
        
        # Verify soft deletion
        db.session.refresh(self.staff)
        self.assertTrue(self.staff.is_deleted)

    def test_delete_employee_self_fails(self):
        self.client.post('/auth/login', data={'username': 'manager_user', 'password': 'managerpass'})
        
        response = self.client.post(f'/employees/{self.manager.id}/delete')
        self.assertEqual(response.status_code, 302)
        
        # Verify NOT deleted
        db.session.refresh(self.manager)
        self.assertFalse(self.manager.is_deleted)

if __name__ == '__main__':
    unittest.main()
