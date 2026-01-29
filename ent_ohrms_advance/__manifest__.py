{
    'name': 'Enterprise OpenHRMS Advance Management',
    'version': '18.0',
    'category': 'Generic Modules/Human Resources',
    'summary': 'Manage Advance Requests',
    'description': """Helps you to manage Advance Requests of your company's 
     staff.""",
    'author': "Muhammad Minhal",
    'depends': [
        'base', 'hr_payroll', 'hr', 'account',
    ],
    'data': [
        'security/hr_advance_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/hr_payslip_input_type_data.xml',
        'views/hr_employee_views.xml',
        'views/hr_advance_views.xml',
        'views/hr_payroll_structure_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_salary_rule_views.xml'
    ],
    # 'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
