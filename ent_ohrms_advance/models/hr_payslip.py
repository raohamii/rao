# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, date, time
from dateutil.relativedelta import relativedelta
import pytz
from datetime import datetime, timedelta
import calendar
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import format_date
from odoo import models, fields
from ast import literal_eval
from odoo.exceptions import UserError, ValidationError

from datetime import datetime

class InheritWizardPayslips(models.TransientModel):
    _inherit="hr.payslip.employees"

    def compute_sheet(self):
        """Generate payslips, incorporating custom attendance and input logic."""
        self.ensure_one()

        if not self.env.context.get('active_id'):
            from_date = fields.Date.to_date(self.env.context.get('default_date_start'))
            end_date = fields.Date.to_date(self.env.context.get('default_date_end'))
            today = fields.date.today()
            first_day = today + relativedelta(day=1)
            last_day = today + relativedelta(day=31)
            if from_date == first_day and end_date == last_day:
                batch_name = from_date.strftime('%B %Y')
            else:
                batch_name = _('From %s to %s', format_date(self.env, from_date), format_date(self.env, end_date))
            payslip_run = self.env['hr.payslip.run'].create({
                'name': batch_name,
                'date_start': from_date,
                'date_end': end_date,
            })
        else:
            payslip_run = self.env['hr.payslip.run'].browse(self.env.context.get('active_id'))

        employees = self.with_context(active_test=False).employee_ids
        if not employees:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))

        # Prevent a payslip_run from having multiple payslips for the same employee
        employees -= payslip_run.slip_ids.employee_id
        success_result = {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.run',
            'views': [[False, 'form']],
            'res_id': payslip_run.id,
        }
        if not employees:
            return success_result

        payslips = self.env['hr.payslip']
        Payslip = self.env['hr.payslip']

        contracts = employees._get_contracts(
            payslip_run.date_start, payslip_run.date_end, states=['open', 'close']
        ).filtered(lambda c: c.active)
        contracts.generate_work_entries(payslip_run.date_start, payslip_run.date_end)
        work_entries = self.env['hr.work.entry'].search([
            ('date_start', '<=', payslip_run.date_end + relativedelta(days=1)),
            ('date_stop', '>=', payslip_run.date_start + relativedelta(days=-1)),
            ('employee_id', 'in', employees.ids),
        ])

        for slip in payslip_run.slip_ids:
            slip_tz = pytz.timezone(slip.contract_id.resource_calendar_id.tz)
            utc = pytz.timezone('UTC')
            date_from = slip_tz.localize(datetime.combine(slip.date_from, time.min)).astimezone(utc).replace(
                tzinfo=None)
            date_to = slip_tz.localize(datetime.combine(slip.date_to, time.max)).astimezone(utc).replace(tzinfo=None)
            payslip_work_entries = work_entries.filtered_domain([
                ('contract_id', '=', slip.contract_id.id),
                ('date_stop', '<=', date_to),
                ('date_start', '>=', date_from),
            ])
            payslip_work_entries._check_undefined_slots(slip.date_from, slip.date_to)

            # Custom logic for attendance validation
            employee_work_entries = self.env['hr.work.entry'].search([
                ('employee_id', '=', slip.employee_id.id),
                ('date_start', '>=', slip.date_from),
                ('date_stop', '<=', slip.date_to)
            ])

            if len(employee_work_entries) == 1:
                raise ValidationError(
                    "Please complete your Work Entries on a daily basis: {}".format(slip.employee_id.display_name))

            for entries in employee_work_entries:
                employee_work_entries_test = self.env['hr.work.entry'].search(
                    [
                        ('date_start', '>=', entries.date_start.date()),
                        ('date_stop', '<=', entries.date_stop.date()),
                        ('employee_id', '=', slip.employee_id.id)
                    ]
                )

                duration_count = sum(all_records.duration for all_records in employee_work_entries_test)
                required_hours_per_day = slip.employee_id.contract_id.resource_calendar_id.hours_per_day - 1.5

                if duration_count < required_hours_per_day:
                    raise ValidationError(
                        f"Please complete your attendance first for {slip.employee_id.display_name} on date {entries.date_start.date()}"
                    )

            # Remove existing EOBI inputs
            # for input_record in slip.input_line_ids:
            #     if 'EOBI' in input_record.display_name:
            #         input_record.unlink()

            # Prepare and add EOBI input line
            # eobi_type = self.env['hr.payslip.input.type'].search([('id', '=', 45)])
            # eobi_amount = self.get_eobi(slip)

            # if eobi_type:
            #     eobi_line = (0, 0, {
            #         'input_type_id': eobi_type.id,
            #         'amount': eobi_amount,
            #         'name': 'EOBI',
            #     })
            #     slip.input_line_ids = [(5, 0, 0)] + [eobi_line]  # Clear existing lines and add new

            # Check for loans and add to input lines
            if not slip.employee_id or not slip.date_from or not slip.date_to:
                continue

            loan_line = slip.struct_id.rule_ids.filtered(lambda x: x.code == 'LO')
            if loan_line:
                approved_loans = self.env['hr.loan'].search([
                    ('employee_id', '=', slip.employee_id.id),
                    ('state', '=', 'approve'),
                    ('loan_line_ids.date', '>=', slip.date_from),
                    ('loan_line_ids.date', '<=', slip.date_to),
                ])

                if approved_loans and ('LO' not in slip.input_line_ids.input_type_id.mapped('code')):
                    for loan in approved_loans:
                        for line in loan.loan_line_ids:
                            if slip.date_from <= line.date <= slip.date_to:
                                amount = line.amount
                                slip.input_data_line(loan_line.id, amount, line)
            # Check for advances and add to input lines
            advance_line = slip.struct_id.rule_ids.filtered(lambda x: x.code == 'AD')
            if advance_line:
                approved_advances = self.env['hr.advance'].search([
                    ('employee_id', '=', slip.employee_id.id),
                    ('state', '=', 'approve'),
                    ('advance_line_ids.date', '>=', slip.date_from),
                    ('advance_line_ids.date', '<=', slip.date_to),
                ])

                if approved_advances and ('AD' not in slip.input_line_ids.input_type_id.mapped('code')):
                    for advance in approved_advances:
                        for line in advance.advance_line_ids:
                            if slip.date_from <= line.date <= slip.date_to:
                                amount = line.amount
                                slip.input_data_line_advance(advance_line.id, amount, line)

        if self.structure_id.type_id.default_struct_id == self.structure_id:
            work_entries = work_entries.filtered(lambda work_entry: work_entry.state != 'validated')
            if work_entries._check_if_error():
                work_entries_by_contract = defaultdict(lambda: self.env['hr.work.entry'])

                for work_entry in work_entries.filtered(lambda w: w.state == 'conflict'):
                    work_entries_by_contract[work_entry.contract_id] |= work_entry

                for contract, work_entries in work_entries_by_contract.items():
                    conflicts = work_entries._to_intervals()
                    time_intervals_str = "\n - ".join(['', *["%s -> %s" % (s[0], s[1]) for s in conflicts._items]])
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Some work entries could not be validated.'),
                        'message': _('Time intervals to look for:%s', time_intervals_str),
                        'sticky': False,
                    }
                }

        default_values = Payslip.default_get(Payslip.fields_get())
        payslips_vals = []
        for contract in self._filter_contracts(contracts):
            values = dict(default_values, **{
                'name': _('New Payslip'),
                'employee_id': contract.employee_id.id,
                'payslip_run_id': payslip_run.id,
                'date_from': payslip_run.date_start,
                'date_to': payslip_run.date_end,
                'contract_id': contract.id,
                'struct_id': self.structure_id.id or contract.structure_type_id.default_struct_id.id,
            })
            payslips_vals.append(values)

        payslips = Payslip.with_context(tracking_disable=True).create(payslips_vals)
        payslips._compute_name()
        payslips.compute_sheet()
        payslip_run.state = 'verify'

        return success_result


class HrPayslip(models.Model):
    """Employee payslip"""
    _inherit = 'hr.payslip'

    def unlink(self):
        # for line in self.input_line_ids:
        #     if line.loan_line_id:
        for line in self.input_line_ids.loan_line_id.loan_id.loan_line_ids:
            line.paid = False
        for line in self.input_line_ids.advance_line_id.advance_id.advance_line_ids:
            line.paid = False
        return super(HrPayslip, self).unlink()

    def compute_sheet(self):
        """gGenerate payslips, incorporating custom attendance and input logic."""

        payslips = self.filtered(lambda slip: slip.state in ['draft', 'verify'])

        # Iterate over each payslip to include custom logic
        for payslip in payslips:
            contract = payslip.employee_id.contract_id
            if contract.work_entry_source == 'attendance':
                # Check if the contract start date is in the beginning or middle of the month
                contract_start_date = contract.date_start
                start_day_of_month = contract_start_date.day
                # if start_day_of_month > 15:
                #     # Skip validation if contract started after the 15th of the month
                #     continuee

                # Custom attendance validation
                employee_work_entries = self.env['hr.work.entry'].search([
                    ('employee_id', '=', payslip.employee_id.id),
                    ('date_start', '>=', payslip.date_from),
                    ('date_stop', '<=', payslip.date_to)
                ])

                if len(employee_work_entries) == 1:
                    raise ValidationError(
                        "Please complete your Work Entries on a daily basis: {}".format(
                            payslip.employee_id.display_name)
                    )

                # Get the first and last day of the month
                first_day_of_month = payslip.date_from.replace(day=1)
                last_day_of_month = payslip.date_to.replace(
                    day=calendar.monthrange(payslip.date_to.year, payslip.date_to.month)[1])

                # Check each day in the month for work entries
                current_day = first_day_of_month
                while current_day <= last_day_of_month:
                    # Skip Sundays
                    if current_day.weekday() == 6:
                        current_day += timedelta(days=1)
                        continue

                    # Check if there is a public holiday on this date
                    if contract_start_date <= current_day:  # Only validate if the contract started before or on the current day
                        public_holiday = self.env['resource.calendar.leaves'].search_count([
                            ('date_from', '<=', current_day),
                            ('date_to', '>=', current_day),
                            ('resource_id', '=', payslip.employee_id.id)
                        ])

                        # Check if the employee is on leave on this date
                        employee_on_leave = self.env['hr.leave'].search_count([
                            ('employee_id', '=', payslip.employee_id.id),
                            ('date_from', '<=', current_day),
                            ('date_to', '>=', current_day),
                            ('state', '=', 'validate')  # Ensure leave is approved
                        ])

                        if not public_holiday and not employee_on_leave:
                            # Check if there are any work entries for the current day
                            employee_work_entries_test = self.env['hr.work.entry'].search([
                                ('date_start', '<=', current_day),
                                ('date_stop', '>=', current_day),
                                ('employee_id', '=', payslip.employee_id.id)
                            ])

                            duration_count = sum(all_records.duration for all_records in employee_work_entries_test)
                            required_hours_per_day = contract.resource_calendar_id.hours_per_day
                            total_time = (required_hours_per_day - 5 / 60)

                            # if duration_count == 0:
                            #     raise ValidationError(
                            #         f"Please complete your attendance first for {payslip.employee_id.display_name} on date {current_day}"
                            #     )

                    current_day += timedelta(days=1)
            # employee_work_entries = self.env['hr.work.entry'].search([
            #     ('employee_id', '=', payslip.employee_id.id),
            #     ('date_start', '>=', payslip.date_from),
            #     ('date_stop', '<=', payslip.date_to)
            # ])
            #
            # if len(employee_work_entries) == 1:
            #     raise ValidationError(
            #         "Please complete your Work Entries on a daily basis: {}".format(payslip.employee_id.display_name))
            #
            # for entries in employee_work_entries:
            #     employee_work_entries_test = self.env['hr.work.entry'].search(
            #         [
            #             ('date_start', '>=', entries.date_start.date()),
            #             ('date_stop', '<=', entries.date_stop.date()),
            #             ('employee_id', '=', payslip.employee_id.id)
            #         ]
            #     )
            #
            #     duration_count = sum(all_records.duration for all_records in employee_work_entries_test)
            #     required_hours_per_day = entries.employee_id.contract_id.resource_calendar_id.hours_per_day
            #     total_time=(required_hours_per_day - 5 / 60)
            #     # Check if the work duration is within 5 minutes of the required hours
            #     if duration_count==0:
            #         raise ValidationError(
            #             f"Please complete your attendance first for {entries.employee_id.display_name} on date {entries.date_start.date()}"
            #         )

            # Remove existing EOBI inputs and prepare to add a new EOBI input line
            # eobi_type = self.env['hr.payslip.input.type'].search([('id', '=', 9)], limit=1)
            # if eobi_type:
            #     eobi_amount = self.get_eobi(payslip)
            #     eobi_line = {
            #         'input_type_id': eobi_type.id,
            #         'amount': eobi_amount,
            #         'name': 'EOBI',
            #     }
            #     existing_eobi_lines = payslip.input_line_ids.filtered(lambda l: l.input_type_id == eobi_type)
            #     existing_eobi_lines.unlink()  # Remove existing EOBI input lines
            #     payslip.input_line_ids = [(0, 0, eobi_line)]

            # Check for loans and add to input lines
            if payslip.employee_id and payslip.date_from and payslip.date_to:
                loan_line = payslip.struct_id.rule_ids.filtered(lambda x: x.code == 'LO')
                if loan_line:
                    # First, delete existing custom loan input lines
                    existing_loan_inputs = payslip.input_line_ids.filtered(lambda l: l.input_type_id.code == 'LO')
                    existing_loan_inputs.unlink()  # Remove existing loan input lines

                    approved_loans = self.env['hr.loan'].search([
                        ('employee_id', '=', payslip.employee_id.id),
                        ('state', '=', 'approve'),
                        ('loan_line_ids.date', '>=', payslip.date_from),
                        ('loan_line_ids.date', '<=', payslip.date_to),
                    ])

                    if approved_loans:
                        for loan in approved_loans:
                            for line in loan.loan_line_ids:
                                if payslip.date_from <= line.date <= payslip.date_to:
                                    lo_type = self.env['hr.payslip.input.type'].search([('code', '=', 'LO')], limit=1)
                                    amount = line.amount
                                    input_data_line = {
                                        'input_type_id': lo_type.id,  # Assuming '8' is the correct ID for Loan Deduction
                                        'amount': amount,
                                        'name': 'Loan Deduction',
                                    }
                                    payslip.input_line_ids = [(0, 0, input_data_line)]

            # Check for advances and add to input lines
            if payslip.employee_id and payslip.date_from and payslip.date_to:
                advance_line = payslip.struct_id.rule_ids.filtered(lambda x: x.code == 'AD')
                if advance_line:
                    # First, delete existing custom advance input lines
                    existing_advance_inputs = payslip.input_line_ids.filtered(
                        lambda l: l.input_type_id.code == 'AD')
                    existing_advance_inputs.unlink()  # Remove existing advance input lines

                    approved_advances = self.env['hr.advance'].search([
                        ('employee_id', '=', payslip.employee_id.id),
                        ('state', '=', 'approve'),
                        ('advance_line_ids.date', '>=', payslip.date_from),
                        ('advance_line_ids.date', '<=', payslip.date_to),
                    ])

                    if approved_advances:
                        for advance in approved_advances:
                            for line in advance.advance_line_ids:
                                if payslip.date_from <= line.date <= payslip.date_to:
                                    amount = line.amount
                                    ad_type = self.env['hr.payslip.input.type'].search([('code', '=', 'AD')], limit=1)
                                    input_data_line = {
                                        'input_type_id': ad_type.id,
                                        # Assuming '11' is the correct ID for advance Deduction
                                        'amount': amount,
                                        'name': 'Advance Deduction',
                                    }
                                    payslip.input_line_ids = [(0, 0, input_data_line)]


        # Delete old payslip lines
        payslips.line_ids.unlink()

        # This guarantees consistent results
        self.env.flush_all()

        today = fields.Date.today()
        for payslip in payslips:
            number = payslip.number or self.env['ir.sequence'].next_by_code('salary.slip')
            payslip.write({
                'number': number,
                'state': 'verify',
                'compute_date': today
            })

        # Create new payslip lines
        self.env['hr.payslip.line'].create(payslips._get_payslip_lines())

        return True

    def action_payslip_done(self):
        """Mark loan as paid on paying payslip"""
        for line in self.input_line_ids:
            if line.loan_line_id:
                # self.loan_id = [(4, [line.loan_line_id.loan_id.id])]
                # self.write({'loan_id': [(4, [line.loan_line_id.loan_id])]})
                # self.update(loan_id=[(4, 0, literal_eval(line.loan_line_id.loan_id))])
                # self.loan_id.append(line.loan_line_id.loan_id)
                line.loan_line_id.loan_id.lines_editable = True
                line.loan_line_id.paid = True
                line.loan_line_id.paid_date = self.date_to
                line.loan_line_id.loan_id._compute_loan_amount()
        """Mark advance as paid on paying payslip"""
        for line in self.input_line_ids:
            if line.advance_line_id:
                # self.advance_id = [(4, [line.advance_line_id.advance_id.id])]
                # self.write({'advance_id': [(4, [line.advance_line_id.advance_id])]})
                # self.update(advance_id=[(4, 0, literal_eval(line.advance_line_id.advance_id))])
                # self.advance_id.append(line.advance_line_id.advance_id)
                line.advance_line_id.advance_id.lines_editable = True
                line.advance_line_id.paid = True
                line.advance_line_id.paid_date = self.date_to
                line.advance_line_id.advance_id._compute_advance_amount()
        return super(HrPayslip, self).action_payslip_done()

    def input_data_line(self, name, amount, loan):
        """Add loan details to payslip as other input"""
        check_lines = []
        new_name = self.env['hr.payslip.input.type'].search([
            ('input_id', '=', 196)])
        line = (0, 0, {
            'input_type_id': new_name.id,
            'amount': amount,
            'name': 'LO',
            'loan_line_id': loan.id
        })
        check_lines.append(line)
        self.input_line_ids = check_lines

    def input_data_line_advance(self, name, amount, advance):
        """Add advance details to payslip as other input"""
        check_lines = []
        new_name = self.env['hr.payslip.input.type'].search([
            ('input_id', '=', 196)])
        line = (0, 0, {
            'input_type_id': new_name.id,
            'amount': amount,
            'name': 'AD',
            'loan_line_id': advance.id
        })
        check_lines.append(line)
        self.input_line_ids = check_lines
