# -*- coding: utf-8 -*-
from datetime import date
from odoo import fields, models
from odoo.exceptions import UserError


class HrAdvance(models.Model):
    """ Inheriting hr.advance for adding fields into the model. """
    _inherit = 'hr.advance'

    employee_account_id = fields.Many2one(comodel_name='account.account',
                                          string="Advance Account",
                                          help="Select employee chart of "
                                               "accounts")
    treasury_account_id = fields.Many2one(comodel_name='account.account',
                                          string="Treasury Account",
                                          help="Select employee treasury "
                                               "account details")
    journal_id = fields.Many2one(comodel_name='account.journal',
                                 string="Journal",
                                 help="Select journal for employee")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_approval_1', 'Submitted'),
        ('waiting_approval_2', 'Waiting Approval'),
        ('approve', 'Approved'),
        ('refuse', 'Refused'),
        ('cancel', 'Canceled'),
    ], string="State", default='draft', track_visibility='onchange',
        copy=False)

    def action_approve(self):
        """ This creates an invoice in account.move with advance request details.
        """
        advance_approve = self.env['ir.config_parameter'].sudo().get_param(
            'account.advance_approve')
        contract_obj = self.env['hr.contract'].search(
            [('employee_id', '=', self.employee_id.id)])
        if not contract_obj:
            raise UserError('You must Define a contract for employee')
        if not self.advance_line_ids:
            raise UserError('You must compute installment before Approved')
        if advance_approve:
            self.write({'state': 'waiting_approval_2'})
        else:
            if (not self.employee_account_id or not self.treasury_account_id or
                    not self.journal_id):
                raise UserError(
                    "You must enter employee account & Treasury account and"
                    " journal to approve ")
            if not self.advance_line_ids:
                raise UserError(
                    'You must compute Advance Request before Approved')
            for advance in self:
                debit_vals = {
                    # 'name': advance.employee_id.name,
                    'name': advance.description,
                    'account_id': advance.treasury_account_id.id,
                    'journal_id': advance.journal_id.id,
                    'date': date.today(),
                    'debit': advance.advance_amount > 0.0 and advance.advance_amount or 0.0,
                    'credit': advance.advance_amount < 0.0 and -advance.advance_amount
                              or 0.0,
                    'advance_id': advance.id,
                }
                credit_vals = {
                    'name': advance.description,
                    'account_id': advance.employee_account_id.id,
                    'journal_id': advance.journal_id.id,
                    'date': date.today(),
                    'debit': advance.advance_amount < 0.0 and
                             -advance.advance_amount or 0.0,
                    'credit': advance.advance_amount > 0.0 and
                              advance.advance_amount or 0.0,
                    'advance_id': advance.id,
                }
                advance_des=''
                if advance.description:
                    advance_des+='Advance For' + ' ' + advance.employee_id.name+' '+str(advance.description)
                else:
                    advance_des+='Advance For' + ' ' + advance.employee_id.name
                vals = {
                    'name': advance_des,
                    'narration': advance.employee_id.name,
                    'ref': advance.name,
                    'journal_id': advance.journal_id.id,
                    # 'date': date.today(),
                    'date': advance.advance_disburse_date,
                    'line_ids': [(0, 0, debit_vals), (0, 0, credit_vals)]
                }
                move = self.env['account.move'].create(vals)
                # move.date = advance.advance_disburse_date
                move.action_post()
            self.write({'state': 'approve'})
        return True

    def action_double_approve(self):
        """ This creates account move for request in case of double approval.
        """
        if (not self.employee_account_id or not self.treasury_account_id or not
        self.journal_id):
            raise UserError(
                "You must enter employee account & Treasury account and "
                "journal to approve ")
        if not self.advance_line_ids:
            raise UserError('You must compute Advance Request before Approved')
        for advance in self:
            debit_vals = {
                'name': advance.employee_id.name,
                'account_id': advance.treasury_account_id.id,
                'journal_id': advance.journal_id.id,
                'date': date.today(),
                'debit': advance.advance_amount > 0.0 and advance.advance_amount or 0.0,
                'credit': advance.advance_amount < 0.0 and -advance.advance_amount or 0.0,
                'advance_id': advance.id,
            }
            credit_vals = {
                'name': advance.employee_id.name,
                'account_id': advance.employee_account_id.id,
                'journal_id': advance.journal_id.id,
                'date': date.today(),
                'debit': advance.advance_amount < 0.0 and -advance.advance_amount or 0.0,
                'credit': advance.advance_amount > 0.0 and advance.advance_amount or 0.0,
                'advance_id': advance.id,
            }
            if advance.description:
                desc='advance For' + ' ' + advance.employee_id.name+' '+ str(advance.description)
            else:
               desc= 'Advance For' + ' ' + advance.employee_id.name + ' '
            vals = {
                'name': desc,
                'narration': advance.employee_id.name,
                'ref': advance.name,
                'journal_id': advance.journal_id.id,
                'date': date.today(),
                'line_ids': [(0, 0, debit_vals), (0, 0, credit_vals)]
            }
            move = self.env['account.move'].create(vals)
            move.action_post()
        self.write({'state': 'approve'})
        return True
