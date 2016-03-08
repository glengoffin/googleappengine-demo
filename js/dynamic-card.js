// Began conversion from jQuery to vanilla JS.
// Setup

var module = {};
module.clickedElementOrder;
module.clickedElementPosition;
module.changeAmount;

for (var i = 0; i < 12; i++) {
    var card = document.createElement('div');
    card.className = "card";
    card.style = "order: " + i;
    document.querySelector('.cardContainer').appendChild(card);
}

// Events

$('body').click(function() { module.reset() });

$('.card').click(function(event) {
    var self = this;
    event.stopPropagation();    
    var promise = module.reset();
    
    promise.done(function() {       
        module.inlineCardMode(self);        
    }, module);
});

// Static Methods

module.addInline = function(cardElement) {
    $(cardElement).after('<div class="inlineCard"></div>');
    
    module.recalculateOrder();
    
    $('.inlineCard').animate({minHeight: '250px', opacity: 1},{duration: 300, queue: true});
}

module.currentCardsPerRow = function() {
    var rowWidth = $('.cardContainer').innerWidth();
    var rowPadding = parseInt($('.cardContainer').css('padding'));
    rowWidth = rowWidth - (rowPadding * 2);
    var cardWidth = $('.card:first-of-type').outerWidth();
    var cardMargin = parseInt($('.card:first-of-type').css('margin'));
    var is3Cards = (rowWidth - (3 * (cardWidth + (2 * cardMargin)))) > 0;
    var is2Cards = (rowWidth - (2 * (cardWidth + (2 * cardMargin)))) > 0;

    if (is3Cards) {
        return 3;
    } else if (is2Cards) {
        return 2;
    } else {
        return 1;
    }
}

module.insertAfterElement = function(cardElement) {
    var perRow = module.currentCardsPerRow();
    module.clickedElementOrder = parseInt(cardElement.style.order);
    module.clickedElementPosition = module.positionInRow(perRow);

    switch (module.clickedElementPosition) {
        case "first":            
            if (perRow === 3) {
                return cardElement.nextElementSibling.nextElementSibling;
            } else if (perRow === 2) {
                return cardElement.nextElementSibling;
            }
            break;
            
        case "middle":
            return cardElement.nextElementSibling;
            break;
            
        case "last":
            return cardElement; 
            
        default:
            return cardElement;
    }
}

module.positionInRow = function(perRow) {
    var mod = (module.clickedElementOrder / perRow) % 1;
    if (perRow === 3) {
        if (module.clickedElementOrder === 0 || mod === 0) {
            module.changeAmount = 3;
            return "first";
        } else if (module.clickedElementOrder === 1 || mod != 0) {
            if (((module.clickedElementOrder + 1) / perRow) % 1 === 0) {
                module.changeAmount = 1;
                return "last";  
            } else {
                module.changeAmount = 2;
                return "middle";            
            }            
        }
    }
    if (perRow === 2) {
        if (module.clickedElementOrder === 0 || mod === 0) {
            module.changeAmount = 2;
            return "first";
        } else {
            module.changeAmount = 1;
            return "last";
        }
    }    
}

module.recalculateOrder = function() {
    var inlineCard = document.querySelector('.inlineCard');

    inlineCard.style.order = module.clickedElementOrder + module.changeAmount;
    
    $('.card').each(function() {
        var thisOrder = parseInt(this.style.order);
        if ( thisOrder >= module.clickedElementOrder + module.changeAmount) {
            this.style.order = thisOrder + module.changeAmount + 1;
        }
    })
}

module.resetOrder = function() {
    var order = 0;
    $('.card').each(function() {
        this.style.order = order;
        order++;
    });
    
    module.clickedElementOrder = null;
    module.clickedElementPosition = null;
    module.changeAmount = null;
}

module.reset = function() {
    $('.card').removeClass('active inactive');
    // without the delay the slidein animation of the next inline card overlaps the slide out of this card
    return $('.inlineCard').animate({minHeight: '0px', opacity: 0}, {duration: 300, queue: true}).delay(400).promise();
}

module.removeInlineCards = function() {
    var inlineCard = document.querySelector('.inlineCard');
    if (inlineCard) {
        document.querySelector('.cardContainer').removeChild(inlineCard);
    } 
}

module.inlineCardMode = function(card) {
    module.removeInlineCards();
    module.resetOrder();
    $('.card').removeClass('active').addClass('inactive');
    $(card).removeClass('inactive').addClass('active');
    module.addInline(module.insertAfterElement(card));
}
