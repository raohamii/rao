# -*- coding: utf-8 -*-
from odoo import fields, models


# class HrPayrollStructure(models.Model):
#     """New field company_id on 'hr.payroll.structure'"""
#     _inherit = 'hr.payroll.structure'
#
#     company_id = fields.Many2one(comodel_name='res.company', string='Company',
#                                  copy=False, readonly=True, help="Company",
#                                  default=lambda self: self.env.user.company_id)
