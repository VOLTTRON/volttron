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
            itemsList: preppedItems
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
    },
    handleClickOutside: function () {
        if (!this.state.hideMenu)
        {
            var validValue = this._validateValue(this.state.inputValue);
            this.props.onselect(validValue);
            this.setState({hideMenu: true});
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
    },
    _onFocus: function () {
        this.setState({hideMenu: false});
    },
    _onKeyup: function (e) {
        if (e.keyCode === 13)
        {
            this.forceHide = true;
            this.setState({hideMenu: true});

            var validValue = this._validateValue(this.state.inputValue);
            this.props.onselect(validValue);
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
            return (
                <div className="combobox-item">
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
                    ref="comboInput"
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
