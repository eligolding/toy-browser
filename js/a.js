var x = 3;

var nodes = document.querySelectorAll('p')
console.log(nodes.map(function(node) { return node.getAttribute('class') }))

var label = document.querySelectorAll("label")[0];
var inputs = document.querySelectorAll('input');
for (var i = 0; i < inputs.length; i++) {
    var input = inputs[i]
    input.addEventListener('keydown', function(e) {
        console.log(this, e)
        var name = this.getAttribute("name");
        var value = this.getAttribute("value");
        label.innerHTML = "Input " + name + " has a value of " + value;
//        console.log("Input " + name + " has a value of " + value)
    })

}


var form = document.querySelectorAll("form")[0];
form.addEventListener("submit", function(e) {
    console.log('you shall not pass!!!')
//    e.preventDefault();
});