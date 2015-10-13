# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#}}}

import sqplatform3

class Sqplatform3Driver:
    def __init__():
        self._con = sqplatform3.connect(':memory:')
        self._cur = con.cursor()
        
    def create_table(self, table_name, columns):
        col_sql = ""
        for col_name, data_type in columns.iteritem():
            col_sql += col_name + " " + data_type
        self._cur.execute("CREATE TABLE " + table_name + " (" + col_sql + ")")
    
    def select_data_all(self, table_name, wheres):
        where_sql = ""
        for cond, oper in wheres.iteritem():
            where_sql += oper + " " + cond
        self._cur.execute("SELECT * FROM " + table_name + " WHERE " + where_sql)

    def insert_data(self, table_name, columns):
        col_sql = ""
        val_sql = ""
        for col_name, val in columns.iteritem():
            col_sql += col_name + ","
            val_sql += val + ","
        col_sql = "(" + col_sql.rstrip(",") + ")"
        val_sql = "(" + val_sql.rstrip(",") + ")"
        self._cur.execute("INSERT INTO " + table_name + col_sql + " " + val_sql)
    
    def update_data(self, table_name, columns, wheres):
        col_sql = ""
        where_sql = ""
        for col_name, val in columns.iteritem():
            col_sql += col_name + "=" + val + ","
        for cond, oper in wheres.iteritem():
            where_sql += oper + " " + cond
        col_sql = col_sql.rstrip(",")
        where_sql = where_sql.rstrip(",")
        self._cur.execute("UPDATE " + table_name + "SET " + col_sql + " WHERE " + where_sql)
        
    def delete_data(self, table_name, wheres):
        for cond, oper in wheres.iteritem():
            where_sql += oper + " " + cond
        self._cur.execute("DELETE FROM " + table_name + " WHERE " + where_sql)
        
        
