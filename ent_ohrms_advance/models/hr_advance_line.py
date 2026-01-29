# -*- coding: utf-8 -*-
from odoo import fields, models, api


class HrPayslipInputType(models.Model):
    """Inherited model for 'hr.payslip.input.type'"""
    _inherit = 'hr.payslip.input.type'

    input_id = fields.Many2one('hr.salary.rule')
    
class HrAdvanceLine(models.Model):
    """
        Class for creating installment details
    """
    _name = "hr.advance.line"
    _description = "Installment Line"

    date = fields.Date(string="Payment Date", required=True,
                       help="Date of the payment")
    paid_date = fields.Date(string="Disburse Date",
                       help="Date of the payment Paid")
    employee_id = fields.Many2one(comodel_name='hr.employee', string="Employee",
                                  help="Employee")
    amount = fields.Float(string="Amount", required=True, help="Amount")
    paid = fields.Boolean(string="Paid", help="Paid")
    advance_id = fields.Many2one(comodel_name='hr.advance', string="Advance Ref.",
                              help="Advance")
    payslip_id = fields.Many2one(comodel_name='hr.payslip',
                                 string="Payslip Ref.",
                                 help="Payslip")

    @api.onchange('amount')
    def _onchange_amount(self):
        if self.amount:
            total_amount = 0
            for line in self.advance_id.advance_line_ids:
                total_amount += line.amount
            self.advance_id.advance_amount = total_amount
