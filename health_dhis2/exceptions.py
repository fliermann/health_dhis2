# SPDX-FileCopyrightText: 2023 Florian Liermann
#
# SPDX-License-Identifier: GPL-3.0-or-later

class DHIS2APIError(Exception):
    pass


class NotFoundError(DHIS2APIError):
    pass


class UnauthorizedError(DHIS2APIError):
    pass


class UnhandledConflictError(DHIS2APIError):
    pass
