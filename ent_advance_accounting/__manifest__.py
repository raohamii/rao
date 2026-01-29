# -*- coding: utf-8 -*-
{
    'name': 'Enterprise OpenHRMS Advance Accounting',
    'version': '18.0',
    'category': 'Generic Modules/Human Resources',
    'summary': 'Open HRMS Advance Accounting',
    'description': """Manage Advance Request of Employees.Double Layer Approval 
     of Hr Department and Accounting.Create accounting entries for Advance 
     requests.""",
    'author': "Muhammad Minhal",
    'depends': [
        'hr_payroll',
        'hr',
        'account',
        'account_accountant',
        'ent_ohrms_advance'
    ],
    'data': [
        'views/hr_advance_views.xml',
        'views/res_config_settings_views.xml',
    ],
    # 'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
