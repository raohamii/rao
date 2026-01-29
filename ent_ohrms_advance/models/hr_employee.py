# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    """ Inheriting hr employee for computing number of advances for employees """
    _inherit = "hr.employee"

    def _compute_advance_count(self):
        """ Compute the number of advances associated with the employee. """
        for record in self:
            record.advance_count = self.env['hr.advance'].search_count(
                [('employee_id', '=', self.id)])

    advance_count = fields.Integer(string="Advance Count", help="Count of Advances.",
                                compute='_compute_advance_count')

    def action_advances(self):
        """ Get the list of advances associated with the current employee.
           This method returns an action that opens a window displaying a tree
           view and form view of advances related to the employee. """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Advances',
            'view_mode': 'list,form',
            'res_model': 'hr.advance',
            'domain': [('employee_id', '=', self.id)],
            'context': "{'create': False}"
        }
