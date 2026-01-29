# -*- coding: utf-8 -*-
################################################################################
#
#    A part of OpenHRMS Project <https://www.openhrms.com>
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Cybrosys Techno Solutions (odoo@cybrosys.com)
#
#    This program is under the terms of the Odoo Proprietary License v1.0
#    (OPL-1)
#    It is forbidden to publish, distribute, sublicense, or sell copies of the
#    Software or modified copies of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#    OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
#    USE OR OTHER DEALINGS IN THE SOFTWARE.
#
################################################################################
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrLoan(models.Model):
    """Model for Loan Requests for employees."""
    _name = 'hr.loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Loan Request"

    @api.model
    def default_get(self, field_list):
        """ Retrieve default values for specified fields. """
        result = super(HrLoan, self).default_get(field_list)
        if result.get('user_id'):
            ts_user_id = result['user_id']
        else:
            ts_user_id = self.env.context.get('user_id', self.env.user.id)
        result['employee_id'] = self.env['hr.employee'].search(
            [('user_id', '=', ts_user_id)], limit=1).id
        return result

    def _compute_loan_amount(self):
        """ calculate the total amount paid towards the loan. """
        total_paid = 0.0
        for loan in self:
            for line in loan.loan_line_ids:
                if line.paid:
                    total_paid += line.amount
            balance_amount = loan.loan_amount - total_paid
            loan.total_amount = loan.loan_amount
            loan.balance_amount = balance_amount
            loan.total_paid_amount = total_paid

    name = fields.Char(string="Loan Name", default="/", readonly=True,
                       help="Name of the loan")
    date = fields.Date(string="Date", default=fields.Date.today(),
                       readonly=True, help="Date")
    employee_id = fields.Many2one(comodel_name='hr.employee', string="Employee",
                                  required=True, help="Employee")
    department_id = fields.Many2one(comodel_name='hr.department',
                                    related="employee_id.department_id",
                                    readonly=True,
                                    string="Department", help="Employee")
    installment = fields.Integer(string="No Of Installments", default=1,
                                 help="Number of installments")
    payment_date = fields.Date(string="Deduction Start Date", required=True,
                               default=fields.Date.today(),
                               help="Date of the Deduction")
    loan_disburse_date = fields.Date(string="Loan Disburse Date",
                               # default=fields.Date.today(),
                               help="Date of the Disburse")
    loan_line_ids = fields.One2many(comodel_name='hr.loan.line',
                                    help="Loan lines",
                                    inverse_name='loan_id', string="Loan Line",
                                    index=True)
    company_id = fields.Many2one(comodel_name='res.company', string='Company',
                                 help="Company",
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one(comodel_name='res.currency',
                                  string='Currency', required=True,
                                  help="Currency",
                                  default=lambda self:
                                  self.env.user.company_id.currency_id)
    job_position_id = fields.Many2one(comodel_name='hr.job',
                                      related="employee_id.job_id",
                                      readonly=True, string="Job Position",
                                      help="Job position")
    loan_amount = fields.Float(string="Loan Amount", required=True,
                               help="Loan amount")
    total_amount = fields.Float(string="Total Amount", store=True,
                                readonly=True, compute='_compute_loan_amount',
                                help="Total loan amount")
    balance_amount = fields.Float(string="Balance Amount", store=True,
                                  compute='_compute_loan_amount',
                                  help="Balance amount")
    total_paid_amount = fields.Float(string="Total Paid Amount", store=True,
                                     compute='_compute_loan_amount',
                                     help="Total paid amount")
    state = fields.Selection([
        ('draft', 'Draft'), ('waiting_approval_1', 'Submitted'),
        ('approve', 'Approved'), ('refuse', 'Refused'), ('cancel', 'Canceled'),
    ], string="State", help="states of loan request", default='draft',
        tracking=True, copy=False, )
    type = fields.Selection([
        ('loan', 'Loan'), ('advance', 'Advance'),
    ], string="Type", default='loan')
    description = fields.Text('Description')
    lines_editable = fields.Boolean(default=False)

    def get_next_month(self, year, month):
        if month == 12:
            year += 1
            month = 1

        d = datetime(year, month, 1)
        return f'{d.month}-{d.year}'

    def get_months(self, date, installments):
        date_list = date.split('-')
        dates = []
        for count in range(installments):
            if count == 0:
                d = datetime(int(date_list[0]), int(date_list[1]),1)
                d_s = f'{d.month}-{d.year}'
                dates.append(d_s)
            else:
                d_s = self.get_next_month(int(date_list[0]), int(date_list[1]))
                dates.append(d_s)
        return dates

    def write(self, data):
        # Check if 'loan_line_ids' is in the data to be updated
        if 'loan_line_ids' in data:
            total_amount = 0
            founded_ids = []

            # Calculate the total amount of existing loan lines
            for line in self.loan_line_ids:
                found = False
                for line2 in data['loan_line_ids']:
                    # If the operation is an update (operation code 1)
                    if line2[0] == 1 and line.id == line2[1]:
                        founded_ids.append(line.id)
                        found = True
                        total_amount += line2[2].get('amount', line.amount)
                # Add amounts of lines that are not updated
                if not found:
                    total_amount += line.amount

            # Calculate the total amount for new loan lines
            for line in data['loan_line_ids']:
                # If the operation is a creation (operation code 0)
                if line[0] == 0 and line[1] not in founded_ids:
                    total_amount += line[2]['amount']

            # Raise a validation error if the total amount does not match the loan amount
            if total_amount != self.loan_amount:
                raise ValidationError(
                    f'Total Loan amount is {self.loan_amount} and your edited loan amount is {total_amount}. Kindly update your record.'
                )

        # Ensure loan disburse date is set before approval
        if (
                self.loan_disburse_date is False
                and self.state == 'waiting_approval_1'
                and 'loan_disburse_date' not in data
        ):
            raise ValidationError('You must have to enter Loan Disburse Date before approval.')

        # Call the superclass's write method to update the record
        res = super(HrLoan, self).write(data)
        return res

    # def write(self, data):
    #     # if 'approve' in data and self.loan_disburse_date == False:
    #
    #     if 'loan_line_ids' in data:
    #         total_amount = 0
    #         founded_ids = []
    #         for line in self.loan_line_ids:
    #             found = False
    #             for line2 in data['loan_line_ids']:
    #                 if line.id == line2[1]:
    #                     founded_ids.append(line.id)
    #                     found = True
    #                     total_amount += line2[2]['amount']
    #             if found == False:
    #                 total_amount += line.amount
    #         for line in data['loan_line_ids']:
    #             if line[1] not in founded_ids:
    #                 total_amount += line[2]['amount']
    #         if total_amount != self.loan_amount:
    #             raise ValidationError(f'Total Loan amount is {self.loan_amount} and your edited loan amount is {total_amount}. Kindly update your record.')
    #             # if amount == line2:
    #             #     [2]['amount']
    #     # if data['loan_line_ids'][0][2]['amount']:
    #     #     pass
    #     if self.loan_disburse_date == False and self.state == 'waiting_approval_1' and 'loan_disburse_date' not in data:
    #         raise ValidationError('You must have to enter Loan Disburse Date before approval.')
    #     res = super(HrLoan, self).write(data)
    #     # self.env.registry.clear_cache()
    #     return res

    @api.model
    def create(self, values):
        """creates a new HR loan record with the provided values."""
        # loans = self.env['hr.loan'].search(
        #     [('employee_id', '=', values['employee_id']),('state', '=', 'approve')])
        # months_list = self.get_months(values['payment_date'], values['installment'])
        # for loan in loans:
        #     for line in loan.loan_line_ids:
        #         for date_string in months_list:
        #             d_s = f'{line.date.month}-{line.date.year}'
        #             if d_s == date_string:
        #                 raise ValidationError('Date Clash: You are entering dates which are already existed in other loan.')

        # # loan_count = self.env['hr.loan'].search_count(
        # #     [('employee_id', '=', values['employee_id']),
        # #      ('state', '=', 'approve'),
        # #      ('balance_amount', '!=', 0)])
        # if loan_count:
        #     raise ValidationError(
        #         _("The employee has already an installment"))
        # else:
        values['name'] = self.env['ir.sequence'].get('hr.loan.seq') or ' '
        res = super(HrLoan, self).create(values)
        return res

    def action_compute_installment(self):
        """This automatically create the installment the employee need to pay
        to company based on payment start date and the no of installments."""
        for loan in self:
            loan.loan_line_ids.unlink()
            date_start = datetime.strptime(str(loan.payment_date), '%Y-%m-%d')
            amount = loan.loan_amount / loan.installment
            for i in range(1, loan.installment + 1):
                self.env['hr.loan.line'].create({
                    'date': date_start,
                    'amount': amount,
                    'employee_id': loan.employee_id.id,
                    'loan_id': loan.id})
                date_start = date_start + relativedelta(months=1)
            loan._compute_loan_amount()
        return True

    def action_refuse(self):
        """Action to refuse the loan"""
        return self.write({'state': 'refuse'})

    def action_submit(self):
        """Action to submit the loan"""
        self.write({'state': 'waiting_approval_1'})

    def action_cancel(self):
        """Action to cancel the loan"""
        self.write({'state': 'cancel'})

    def action_approve(self):
        """Approve loan by the manager"""
        for data in self:
            if not data.loan_line_ids:
                raise ValidationError(_("Please Compute installment"))
            else:
                self.write({'state': 'approve'})

    def unlink(self):
        """Unlink loan lines"""
        for loan in self:
            if loan.state not in ('draft', 'cancel'):
                raise UserError(
                    'You cannot delete a loan which is not in draft or '
                    'cancelled state')
        return super(HrLoan, self).unlink()
