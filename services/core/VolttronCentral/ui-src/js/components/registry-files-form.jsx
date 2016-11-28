'use strict';


import React from 'react';
import BaseComponent from './base-component';

var devicesActionCreators = require('../action-creators/devices-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesStore = require('../stores/devices-store');

class RegistryFilesForm extends BaseComponent {   
    constructor(props) {
        super(props);
        this._bind("_loadRegistryFile", "_closeModal", "_onStoresChange");

        this.state = {
            registryFiles: devicesStore.getSavedRegistryFiles()
        };
    }
    componentDidMount() {
        devicesStore.addChangeListener(this._onStoresChange);        
    }
    componentWillUnmount() {
        devicesStore.removeChangeListener(this._onStoresChange);
    }
    _onStoresChange() {
        this.setState({ registryFiles: devicesStore.getSavedRegistryFiles()});
    }
    _loadRegistryFile (registryFile) {
        devicesActionCreators.loadRegistryFile(
            registryFile, 
            this.props.device
        );

        modalActionCreators.closeModal();
    }
    _closeModal (e) {
        if (e.target === e.currentTarget)
        {
            modalActionCreators.closeModal();
        }
    }
    render() {

        var filesList;

        if (this.state.registryFiles)
        {    
            filesList = this.state.registryFiles.files.map(function (registryFile) {

                return (
                    <div key={registryFile + "-rf"}
                        className="registry-file"
                        onClick={this._loadRegistryFile.bind(this, registryFile)}>           
                        <div>
                            <i className="fa fa-file"></i>
                        </div>
                        <div>
                            {registryFile}
                        </div>
                    </div>
                );
            }, this);
        }

        return (
            <div className="registryFilesList">
                <h3>Previously Configured Registry Files</h3>
                <div>
                    {filesList}
                </div>
            </div>
        );
    }
};

module.exports = RegistryFilesForm;
