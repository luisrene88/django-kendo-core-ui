$(document).ready(function() {

	$(':input[type=text]').each(function(index, value){
      var id = $(value).attr('id')
			var idf = "#"+id;
      $(idf).addClass('k-textbox');
	});

});
