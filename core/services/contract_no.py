from django.db import IntegrityError, transaction
from django.utils import timezone

from core import models


class ContractNoOverflowError(Exception):
    pass


def _today_prefix(sequence_date):
    return sequence_date.strftime('%Y%m%d')


def _existing_max_serial(prefix):
    max_serial = 0
    for value in models.Contract.objects.filter(contract_no__startswith=prefix).values_list('contract_no', flat=True):
        if not value or len(value) != 11 or not value.isdigit():
            continue
        if not value.startswith(prefix):
            continue
        serial = int(value[-3:])
        if 1 <= serial <= 999 and serial > max_serial:
            max_serial = serial
    return max_serial


def generate_next_contract_no():
    sequence_date = timezone.localdate()
    prefix = _today_prefix(sequence_date)

    while True:
        with transaction.atomic():
            try:
                sequence = models.ContractNoSequence.objects.select_for_update().get(sequence_date=sequence_date)
            except models.ContractNoSequence.DoesNotExist:
                baseline = _existing_max_serial(prefix)
                try:
                    sequence = models.ContractNoSequence.objects.create(
                        sequence_date=sequence_date,
                        last_serial=baseline,
                    )
                except IntegrityError:
                    continue
                sequence = models.ContractNoSequence.objects.select_for_update().get(pk=sequence.pk)

            if sequence.last_serial >= 999:
                raise ContractNoOverflowError('当天合同编号流水号已用尽（999）。')

            sequence.last_serial += 1
            sequence.save(update_fields=['last_serial', 'updated_at'])
            return f"{prefix}{sequence.last_serial:03d}"
