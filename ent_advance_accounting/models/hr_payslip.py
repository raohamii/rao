# -*- coding: utf-8 -*-
import babel
from datetime import datetime, time
from odoo import fields, models, tools


class HrPayslip(models.Model):
    """ Class for inheriting hr payslip. """
    _inherit = 'hr.payslip'

    def action_payslip_done(self):
        """
           The function mark the loan as paid and call the action paid amount
           function for creating an invoice.
        """
        for line in self.input_line_ids:
            date_from = self.date_from
            tym = datetime.combine(fields.Date.from_string(date_from),
                                   time.min)
            locale = self.env.context.get('lang') or 'en_US'
            month = tools.ustr(
                babel.dates.format_date(date=tym, format='MMMM-y',
                                        locale=locale))
            if line.loan_line_id:
                line.loan_line_id.action_paid_amount(month)
            if line.advance_line_id:
                line.advance_line_id.action_paid_amount(month)
        return super(HrPayslip, self).action_payslip_done()
