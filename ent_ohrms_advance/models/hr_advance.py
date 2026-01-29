# -*- coding: utf-8 -*-
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrAdvance(models.Model):
    """Model for Advance Requests for employees."""
    _name = 'hr.advance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Advance Request"

    @api.model
    def default_get(self, field_list):
        """ Retrieve default values for specified fields. """
        result = super(HrAdvance, self).default_get(field_list)
        if result.get('user_id'):
            ts_user_id = result['user_id']
        else:
            ts_user_id = self.env.context.get('user_id', self.env.user.id)
        result['employee_id'] = self.env['hr.employee'].search(
            [('user_id', '=', ts_user_id)], limit=1).id
        return result

    def _compute_advance_amount(self):
        """ calculate the total amount paid towards the advance. """
        total_paid = 0.0
        for advance in self:
            for line in advance.advance_line_ids:
                if line.paid:
                    total_paid += line.amount
            balance_amount = advance.advance_amount - total_paid
            advance.total_amount = advance.advance_amount
            advance.balance_amount = balance_amount
            advance.total_paid_amount = total_paid

    name = fields.Char(string="Advance Name", default="/", readonly=True,
                       help="Name of the advance")
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
    advance_disburse_date = fields.Date(string="Advance Disburse Date",
                               # default=fields.Date.today(),
                               help="Date of the Disburse")
    advance_line_ids = fields.One2many(comodel_name='hr.advance.line',
                                    help="Advance lines",
                                    inverse_name='advance_id', string="Advance Line",
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
    advance_amount = fields.Float(string="Advance Amount", required=True,
                               help="Advance amount")
    total_amount = fields.Float(string="Total Amount", store=True,
                                readonly=True, compute='_compute_advance_amount',
                                help="Total advance amount")
    balance_amount = fields.Float(string="Balance Amount", store=True,
                                  compute='_compute_advance_amount',
                                  help="Balance amount")
    total_paid_amount = fields.Float(string="Total Paid Amount", store=True,
                                     compute='_compute_advance_amount',
                                     help="Total paid amount")
    state = fields.Selection([
        ('draft', 'Draft'), ('waiting_approval_1', 'Submitted'),
        ('approve', 'Approved'), ('refuse', 'Refused'), ('cancel', 'Canceled'),
    ], string="State", help="states of advance request", default='draft',
        tracking=True, copy=False, )
    type = fields.Selection([
        ('loan', 'Loan'), ('advance', 'Advance'),
    ], string="Type", default='advance')
    description = fields.Text('Description')
    lines_editable = fields.Boolean(default=False)


    @api.onchange('installment')
    def onchange_installment(self):
        for rec in self:
            if rec.installment > 1:
                raise ValidationError('Advance installment must be 1.')
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
        # Check if 'advance_line_ids' is in the data to be updated
        if 'advance_line_ids' in data:
            total_amount = 0
            founded_ids = []

            # Calculate the total amount of existing advance lines
            for line in self.advance_line_ids:
                found = False
                for line2 in data['advance_line_ids']:
                    # If the operation is an update (operation code 1)
                    if line2[0] == 1 and line.id == line2[1]:
                        founded_ids.append(line.id)
                        found = True
                        total_amount += line2[2].get('amount', line.amount)
                # Add amounts of lines that are not updated
                if not found:
                    total_amount += line.amount

            # Calculate the total amount for new advance lines
            for line in data['advance_line_ids']:
                # If the operation is a creation (operation code 0)
                if line[0] == 0 and line[1] not in founded_ids:
                    total_amount += line[2]['amount']

            # Raise a validation error if the total amount does not match the advance amount
            if total_amount != self.advance_amount:
                raise ValidationError(
                    f'Total Advance amount is {self.advance_amount} and your edited advance amount is {total_amount}. Kindly update your record.'
                )

        # Ensure advance disburse date is set before approval
        if (
                self.advance_disburse_date is False
                and self.state == 'waiting_approval_1'
                and 'advance_disburse_date' not in data
        ):
            raise ValidationError('You must have to enter Advance Disburse Date before approval.')

        # Call the superclass's write method to update the record
        res = super(HrAdvance, self).write(data)
        return res

    # def write(self, data):
    #     # if 'approve' in data and self.advance_disburse_date == False:
    #
    #     if 'advance_line_ids' in data:
    #         total_amount = 0
    #         founded_ids = []
    #         for line in self.advance_line_ids:
    #             found = False
    #             for line2 in data['advance_line_ids']:
    #                 if line.id == line2[1]:
    #                     founded_ids.append(line.id)
    #                     found = True
    #                     total_amount += line2[2]['amount']
    #             if found == False:
    #                 total_amount += line.amount
    #         for line in data['advance_line_ids']:
    #             if line[1] not in founded_ids:
    #                 total_amount += line[2]['amount']
    #         if total_amount != self.advance_amount:
    #             raise ValidationError(f'Total advance amount is {self.advance_amount} and your edited advance amount is {total_amount}. Kindly update your record.')
    #             # if amount == line2:
    #             #     [2]['amount']
    #     # if data['advance_line_ids'][0][2]['amount']:
    #     #     pass
    #     if self.advance_disburse_date == False and self.state == 'waiting_approval_1' and 'advance_disburse_date' not in data:
    #         raise ValidationError('You must have to enter advance Disburse Date before approval.')
    #     res = super(HrAdvance, self).write(data)
    #     # self.env.registry.clear_cache()
    #     return res

    @api.model
    def create(self, values):
        """creates a new HR advance record with the provided values."""
        # advances = self.env['hr.advance'].search(
        #     [('employee_id', '=', values['employee_id']),('state', '=', 'approve')])
        # months_list = self.get_months(values['payment_date'], values['installment'])
        # for advance in advances:
        #     for line in advance.advance_line_ids:
        #         for date_string in months_list:
        #             d_s = f'{line.date.month}-{line.date.year}'
        #             if d_s == date_string:
        #                 raise ValidationError('Date Clash: You are entering dates which are already existed in other advance.')

        # # advance_count = self.env['hr.advance'].search_count(
        # #     [('employee_id', '=', values['employee_id']),
        # #      ('state', '=', 'approve'),
        # #      ('balance_amount', '!=', 0)])
        # if advance_count:
        #     raise ValidationError(
        #         _("The employee has already an installment"))
        # else:
        values['name'] = self.env['ir.sequence'].get('hr.advance.seq') or ' '
        res = super(HrAdvance, self).create(values)
        return res

    def action_compute_installment(self):
        """This automatically create the installment the employee need to pay
        to company based on payment start date and the no of installments."""
        for advance in self:
            advance.advance_line_ids.unlink()
            date_start = datetime.strptime(str(advance.payment_date), '%Y-%m-%d')
            amount = advance.advance_amount / advance.installment
            for i in range(1, advance.installment + 1):
                self.env['hr.advance.line'].create({
                    'date': date_start,
                    'amount': amount,
                    'employee_id': advance.employee_id.id,
                    'advance_id': advance.id})
                date_start = date_start + relativedelta(months=1)
            advance._compute_advance_amount()
        return True

    def action_refuse(self):
        """Action to refuse the advance"""
        return self.write({'state': 'refuse'})

    def action_submit(self):
        """Action to submit the advance"""
        self.write({'state': 'waiting_approval_1'})

    def action_cancel(self):
        """Action to cancel the advance"""
        self.write({'state': 'cancel'})

    def action_approve(self):
        """Approve advance by the manager"""
        for data in self:
            if not data.advance_line_ids:
                raise ValidationError(_("Please Compute installment"))
            else:
                self.write({'state': 'approve'})

    def unlink(self):
        """Unlink advance lines"""
        for advance in self:
            if advance.state not in ('draft', 'cancel'):
                raise UserError(
                    'You cannot delete a advance which is not in draft or '
                    'cancelled state')
        return super(HrAdvance, self).unlink()
