# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslipInput(models.Model):
    """Inherited model for 'hr.payslip.input'"""
    _inherit = 'hr.payslip.input'

    advance_line_id = fields.Many2one(comodel_name='hr.advance.line',
                                   string="Advance Installment",
                                   help="Advance installment")
