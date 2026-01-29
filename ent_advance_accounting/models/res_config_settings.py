# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """ Inheriting res config settings for adding fields. """
    _inherit = 'res.config.settings'

    advance_approve = fields.Boolean(default=False,
                                  config_parameter="account.advance_approve",
                                  string="Approval from Accounting Department",
                                  help="Advance Approval from account manager")
