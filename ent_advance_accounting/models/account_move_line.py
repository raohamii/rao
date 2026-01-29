# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMoveLine(models.Model):
    """ Inheriting account move line for adding field. """
    _inherit = "account.move.line"

    advance_id = fields.Many2one(comodel_name='hr.advance', string='Advance Id',
                              help="Select advance details for employees")
