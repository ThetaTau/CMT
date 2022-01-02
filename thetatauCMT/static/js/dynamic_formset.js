function updateConditionRow(){
  var conditionRow = $('.row_form:not(:last)');
    conditionRow.find('.btn.add-row_form')
    .removeClass('btn-success').addClass('btn-danger')
    .removeClass('add-row_form').addClass('remove-row_form')
    .html('-');
}
$(function(){
  var dels = $('.row_form input[id $= "-DELETE"]:checked');
  if (dels.length){
    dels.each(function() {
        var row = $(this).closest('.row_form');
        row.hide();
    });
  }
})
$(document).ready(updateConditionRow);
function todayDate(year_add) {
    var d = new Date(),
        month = '' + (d.getMonth() + 1),
        day = '' + d.getDate(),
        year = d.getFullYear() + year_add;

    if (month.length < 2) month = '0' + month;
    if (day.length < 2) day = '0' + day;

    return [year, month, day].join('-');
}
function cloneMore(selector, prefix) {
    var newElement = $(selector).clone();
    var total = $('#id_' + prefix + '-TOTAL_FORMS').val();
    newElement.find('.form-control').each(function() {
        var old_name = $(this).attr('name');
        var name = $(this).attr('name').replace('-' + (total-1) + '-', '-' + total + '-');
        var id = 'id_' + name;
        $(this).attr({'name': name, 'id': id}).val('').removeAttr('checked');
        if ($(this).attr('data-target')){
          var old_id = '#id_' + old_name;
          $(this).attr({'data-target': "#" + id});
          var old_text = $(this).parent('div').parent('div').find('script')[0].text;
          $(this).parent('div').parent('div').find('script')[0].text = old_text.replace(old_id, "#" + id);
          var date = $(this)[0].id.includes('start') ? todayDate(0):todayDate(1);
          $(this).datetimepicker({"format": "M/DD/YYYY", "date": date})
        }
    });
    newElement.find('.form-control-file').each(function () {
        var old_name = $(this).attr('name');
        var name = $(this).attr('name').replace('-' + (total - 1) + '-', '-' + total + '-');
        var id = 'id_' + name;
        $(this).attr({'name': name, 'id': id}).val('').removeAttr('checked');
        if ($(this).attr('data-target')) {
            var old_id = '#id_' + old_name;
            $(this).attr({'data-target': "#" + id});
            var old_text = $(this).parent('div').parent('div').find('script')[0].text;
            $(this).parent('div').parent('div').find('script')[0].text = old_text.replace(old_id, "#" + id);
            var date = $(this)[0].id.includes('start') ? todayDate(0) : todayDate(1);
            $(this).datetimepicker({"format": "M/DD/YYYY", "date": date})
        }
    });
    total++;
    $('#id_' + prefix + '-TOTAL_FORMS').val(total);
    $(selector).after(newElement);
    updateConditionRow();
    return false;
}
function deleteForm(prefix, btn) {
    var total = parseInt($('#id_' + prefix + '-TOTAL_FORMS').val());
    if (total > 1){
        var row = btn.closest('.row_form');
        row.hide();
        var del = row.find('input[id $= "-DELETE"]');
        del.prop('checked', true);
// https://github.com/elo80ka/django-dynamic-formset/blob/master/src/jquery.formset.js
    }
    return false;
}
$(document).on('click', '.add-row_form', function(e){
    e.preventDefault();
    cloneMore('.row_form:last', 'form');
    return false;
});
$(document).on('click', '.remove-row_form', function(e){
    e.preventDefault();
    deleteForm('form', $(this));
    return false;
});
