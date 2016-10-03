'use strict';

var React = require('react');

var ComboBox = React.createClass({
    mixins: [
        require('react-onclickoutside')
    ],
	getInitialState: function () {

        var preppedItems = prepItems(this.props.itemskey, this.props.itemsvalue, this.props.itemslabel, this.props.items);

        var state = {
            selectedKey: "",
            selectedLabel: "",
            selectedValue: "",
            inputValue: "",
            hideMenu: true,
            preppedItems: preppedItems,
            itemsList: preppedItems,
            focusedIndex: -1
        };

        this.forceHide = false;

        return state;
    },
    componentDidUpdate: function () {
        if (this.forceHide)
        {
            React.findDOMNode(this.refs.comboInput).blur();
            this.forceHide = false;
        }
        else
        {
            if (this.state.focusedIndex > -1)
            {
                var modal = document.querySelector(".modal__dialog");

                var comboItems = document.querySelectorAll(".combobox-item");

                if (comboItems.length > this.state.focusedIndex)
                {
                    var targetItem = comboItems[this.state.focusedIndex];

                    if (targetItem)
                    {
                        var menu = targetItem.parentNode;

                        var menuRect = menu.getBoundingClientRect();
                        var modalRect = modal.getBoundingClientRect();
                        var targetRect = targetItem.getBoundingClientRect();

                        if (targetRect.bottom > modalRect.bottom || targetRect.top < modalRect.top)
                        {
                            var newTop = targetRect.top - menuRect.top;

                            modal.scrollTop = newTop;
                        }
                    }

                }
            }
        }
    },
    handleClickOutside: function () {
        if (!this.state.hideMenu)
        {
            var validValue = this._validateValue(this.state.inputValue);
            this.props.onselect(validValue);
            this.setState({hideMenu: true});
            this.setState({focusedIndex: -1});
        }
    },
    _validateValue: function (inputValue) {

        var validInput = this.props.items.find(function (item) {
            return item.label === inputValue;
        });

        var validKey = (validInput ? validInput.key : "");
        var validValue = (validInput ? validInput.value : "");
        var validLabel = (validInput ? validInput.label : "");
        
        this.setState({selectedKey: validKey});
        this.setState({selectedValue: validValue});
        this.setState({selectedLabel: validLabel});

        return validValue;
    },
    _onClick: function (e) {
        this.setState({selectedKey: e.target.dataset.key});
        this.setState({selectedLabel: e.target.dataset.label});
        this.setState({selectedValue: e.target.dataset.value});
        this.setState({inputValue: e.target.dataset.label});
        this.setState({hideMenu: true});

        this.props.onselect(e.target.dataset.value);

        this.setState({focusedIndex: -1});
    },
    _onFocus: function () {
        this.setState({hideMenu: false});
    },
    _onKeyup: function (e) {
        switch (e.keyCode)
        {
            case 13:    //Enter key
                this.forceHide = true;
                this.setState({hideMenu: true});

                var inputValue = this.state.inputValue;

                if (this.state.focusedIndex > -1)
                {
                    var selectedItem = this.state.itemsList[this.state.focusedIndex];
                    inputValue = selectedItem.label;

                    this.setState({inputValue: inputValue});
                    this.setState({selectedKey: selectedItem.key});
                    this.setState({selectedLabel: selectedItem.label});
                    this.setState({selectedValue: selectedItem.value});
                }

                var validValue = this._validateValue(inputValue);
                this.props.onselect(validValue);

                this.setState({focusedIndex: -1});
                break;
        }
    },
    _onKeydown: function (e) {
        switch (e.keyCode)
        {
            case 9:    //Tab key
            case 40:    //Arrow down key

                e.preventDefault();

                var newIndex = 0;

                if (this.state.focusedIndex < this.state.itemsList.length - 1)
                {
                    newIndex = this.state.focusedIndex + 1;
                }

                this.setState({focusedIndex: newIndex});
                break;
            case 38:    //Arrow up key

                e.preventDefault();

                var newIndex = this.state.itemsList.length - 1;

                if (this.state.focusedIndex > 0)
                {
                    newIndex = this.state.focusedIndex - 1;
                }                

                this.setState({focusedIndex: newIndex});
                break;
        }
    },
    _onChange: function (e) {

        var inputValue = e.target.value;

        var itemsList = filterItems(inputValue, this.state.preppedItems);

        this.setState({itemsList: itemsList});

        this.setState({inputValue: inputValue}); 
                
    },

	render: function () {
		
        var menuStyle = {
            display: (this.state.hideMenu ? 'none' : 'block')
        };

        var inputStyle = {
            width: "390px"
        };

        var items = this.state.itemsList.map(function (item, index) {

            var highlightStyle = {};

            if (this.state.focusedIndex > -1 && this.state.focusedIndex === index)
            {
                highlightStyle.backgroundColor = "#B2C9D1"
            }

            return (
                <div className="combobox-item"
                    style={highlightStyle}>
                    <div 
                        onClick={this._onClick}
                        data-label={item.label}
                        data-value={item.value}
                        data-key={item.key}>{item.label}</div>
                </div>
            )
        }, this);

		return (
		
        	<div className="combobox-control">
                <input 
                    style={inputStyle}
                    type="text" 
                    onFocus={this._onFocus} 
                    onChange={this._onChange}
                    onKeyUp={this._onKeyup}
                    onKeyDown={this._onKeydown}
                    ref="comboInput"
                    placeholder="type here to see topics"
                    value={this.state.inputValue}></input>

                <div className="combobox-menu" style={menuStyle}>                    
				    {items}
                </div>
			</div>
		);
	},
});

function prepItems(itemsKey, itemsValue, itemsLabel, itemsList)
{
    var props = {
        itemsKey: itemsKey,
        itemsValue: itemsValue,
        itemsLabel: itemsLabel
    };

    var list = itemsList.map(function (item, index) {

        var preppedItem = {
            key: (this.itemsKey ? item[this.itemsKey] : index),
            value: (this.itemsValue ? item[this.itemsValue] : item),
            label: (this.itemsLabel ? item[this.itemsLabel] : item)
        };

        return preppedItem;
    }, props);

    return JSON.parse(JSON.stringify(list));
}

function filterItems(filterTerm, itemsList)
{
    var listCopy = JSON.parse(JSON.stringify(itemsList));

    var filteredItems = listCopy;

    if (filterTerm)
    {
        filteredItems = [];

        listCopy.forEach(function (item) {
            if (item.label.toUpperCase().indexOf(filterTerm.toUpperCase()) > -1)
            {
                filteredItems.push(item);
            }
        });
    }

    return filteredItems;
}


module.exports = ComboBox;
